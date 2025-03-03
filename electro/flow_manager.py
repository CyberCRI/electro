"""Flow Manager, the main object that manages all the `Flow`s."""

from __future__ import annotations

import typing
from collections import defaultdict

from enums import ChannelType

from . import types_ as types
from ._common import ContextInstanceMixin
from .bot import bot as global_bot
from .exceptions import EventCannotBeProcessed
from .flow import Flow, FlowConnector, FlowFinished
from .flow_connector import FlowConnectorEvents

# from decorators import fail_safely
from .models import Channel, Interaction, Message, User, UserStateChanged
from .scopes import FlowScopes
from .settings import settings
from .storage import BaseFlowStorage, ChannelData, FlowMemoryStorage, UserData
from .toolkit.loguru_logging import logger
from .toolkit.tortoise_orm import Model


class AnalyticsManager(ContextInstanceMixin):
    """The object that manages the analytics."""

    def __init__(self, flow_manager: FlowManager):
        self.flow_manager = flow_manager

        # Set the current analytics manager
        self.set_current(self)

    @staticmethod
    async def save_user(user: types.User, guild: types.Guild | None = None) -> User:
        """Save the user to the database."""
        user, created = await User.get_or_create(
            id=user.id,
            defaults={
                "username": user.username,
                "discriminator": user.discriminator,
                "avatar": user.avatar.get("url") if user.avatar else None,
                "guild_id": guild.id if guild else None,
            },
        )

        if created:
            logger.info(f"Created the User record for {user.id=}, {user.username=}, and {user.discriminator}")

        return user

    @staticmethod
    async def save_channel(channel: types.Channel) -> Channel:
        """Save the channel to the database."""
        return await Channel.create(
            id=channel.id,
            name=getattr(channel, "name", None),
            guild_id=channel.guild.id if getattr(channel, "guild", None) else None,
            type=channel.type,
        )

    async def save_new_member(self, member: types.Member) -> User:
        """Save the new member to the database."""
        # noinspection PyProtectedMember
        user = member._user
        user_obj = await self.save_user(user, member.guild)

        # TODO: [05.06.2024 by Mykola] Save the new member to the database

        return user_obj

    async def save_updated_member(self, before: types.Member, after: types.Member) -> User:
        """Save the updated member to the database."""
        # noinspection PyProtectedMember
        user = after._user
        user_obj = await self.save_user(user, after.guild)

        # TODO: [05.06.2024 by Mykola] Save the updated member to the database

        return user_obj

    async def _get_user_obj(self, user: types.User, guild: types.Guild | None = None) -> User:
        if not (user_obj := await User.get_or_none(id=user.id)):
            logger.warning(f"User {user.id} not found in the database. Creating the user record.")
            user_obj: User = await self.save_user(user, guild)

        return user_obj

    async def _get_channel_obj(self, channel: types.Channel) -> Channel:
        if not (channel_obj := await Channel.get_or_none(id=channel.id)):
            logger.warning(f"Channel {channel.id} not found in the database. Creating the channel record.")
            channel_obj: Channel = await self.save_channel(channel)

        return channel_obj

    async def get_or_save_message(self, message: types.Message) -> Message:
        """Save the message to the database."""
        # Get the user and channel objects (make sure they exist in the database)
        # TODO: [2024-12-23 by Mykola] Add the `.guild` to the `message` object
        # user_obj = await self._get_user_obj(message.author, message.guild)
        user_obj = await self._get_user_obj(message.author, None)
        channel_obj = await self._get_channel_obj(message.channel)

        if message_obj := await Message.get_or_none(id=message.id):
            return message_obj

        return await Message.create(
            id=message.id,
            content=message.content,
            author=user_obj,
            channel=channel_obj,
            created_at=message.created_at,
            edited_at=message.edited_at,
            # TODO: [2024-12-23 by Mykola] Expand the message model
            # is_pinned=message.pinned,
            # is_tts=message.tts,
            # is_bot_message=message.author.bot,
            is_command=message.content.startswith(settings.BOT_COMMAND_PREFIX),
        )

    async def save_interaction(
        self, interaction: types.Interaction, return_message_obj=False
    ) -> Interaction | tuple[Interaction, Message]:
        """Save the interaction to the database."""
        # Get the user and channel objects (make sure they exist in the database)
        user_obj = await self._get_user_obj(interaction.user, interaction.guild)
        channel_obj = await self._get_channel_obj(interaction.channel)

        message_obj = await self.get_or_save_message(interaction.message)

        interaction_obj: Interaction = await Interaction.create(
            id=interaction.id,
            user=user_obj,
            channel=channel_obj,
            message=message_obj,
            custom_id=interaction.data.get("custom_id"),
        )

        if return_message_obj:
            return interaction_obj, message_obj

        return interaction_obj

    async def save_user_state_changed(
        self, user: types.User, previous_state: str | None, new_state: str | None
    ) -> UserStateChanged | None:
        """Save the user state changed record to the database."""
        if previous_state == new_state:
            return

        # Get the user object (make sure it exists in the database)
        user_obj = await self._get_user_obj(user)  # TODO: [2024-10-16 by Mykola] Should be pass `guild` here?

        return await UserStateChanged.create(
            user=user_obj,
            previous_state=previous_state,
            new_state=new_state,
        )


class FlowManager(ContextInstanceMixin):
    """The main object that manages all the `Flow`s."""

    _storage__user_model: Model = User
    _storage__channel_model: Model = Channel

    def __init__(
        self,
        bot: types.Bot,
        flows: typing.Optional[list[Flow]] = None,
        storage: typing.Optional[BaseFlowStorage] = None,
        on_finish_callbacks: typing.Optional[list[typing.Callable[[FlowConnector], typing.Awaitable[None]]]] = None,
    ):
        self.bot = bot
        self.flows: list[Flow] = flows or []

        self.storage = storage or FlowMemoryStorage()
        self.analytics_manager = AnalyticsManager(self)

        self._on_finish_callbacks: list[typing.Callable[[FlowConnector], typing.Awaitable[None]]] = (
            on_finish_callbacks or []
        )

        # Set the current flow manager
        self.set_current(self)

    # region User State and Data management
    async def _get_user_state(self, user: types.User) -> str | None:
        """Get the state of the user."""
        return await self.storage.get_user_state(user.id)

    async def _set_user_state(self, user: types.User, state: str | None):
        """Set the state of the user."""
        # Save the state to the database
        old_state = await self._get_user_state(user)
        if old_state != state:
            await self.analytics_manager.save_user_state_changed(user, old_state, state)
        await self.storage.set_user_state(user.id, state)

    async def _delete_user_state(self, user: types.User):
        """Delete the state of the user."""
        old_state = await self._get_user_state(user)
        if old_state:
            await self.analytics_manager.save_user_state_changed(user, old_state, None)
        await self.storage.delete_user_state(user.id)

    async def _get_user_data(self, user: types.User) -> UserData:
        """Get the data of the user."""
        return await self.storage.get_user_data(user.id)

    async def _set_user_data(self, user: types.User, data: UserData | dict[str, typing.Any] | None):
        """Set the data of the user."""
        await self.storage.set_user_data(user.id, data)

    async def _delete_user_data(self, user: types.User):
        """Delete the data of the user."""
        await self.storage.delete_user_data(user.id)

    # endregion

    # region Channel State and Data management
    async def _get_channel_state(self, channel: types.Channel) -> str | None:
        """Get the state of the channel."""
        return await self.storage.get_channel_state(channel.id)

    async def _set_channel_state(self, channel: types.Channel, state: str | None):
        """Set the state of the channel."""
        await self.storage.set_channel_state(channel.id, state)

    async def _delete_channel_state(self, channel: types.Channel):
        """Delete the state of the channel."""
        await self.storage.delete_channel_state(channel.id)

    async def _get_channel_data(self, channel: types.Channel) -> ChannelData:
        """Get the data of the channel."""
        return await self.storage.get_channel_data(channel.id)

    async def _set_channel_data(self, channel: types.Channel, data: ChannelData | dict[str, typing.Any] | None):
        """Set the data of the channel."""
        await self.storage.set_channel_data(channel.id, data)

    async def _delete_channel_data(self, channel: types.Channel):
        """Delete the data of the channel."""
        await self.storage.delete_channel_data(channel.id)

    # endregion

    # region Flow management
    def add_flow(self, flow: Flow):
        """Add the flow to the manager."""
        self.flows.append(flow)

    def set_flows(self, flows: list[Flow]):
        """Set the flows to the manager."""
        self.flows = flows

    def get_flow(self, flow_name: str) -> Flow | None:
        """Get the flow by its name."""
        for flow in self.flows:
            if flow.__class__.__name__ == flow_name:
                return flow

        return None

    # endregion

    async def _finish_flow(self, flow_connector: FlowConnector):
        """Finish the flow."""
        # Delete the state and data for the user
        await self.storage.delete_user_state(flow_connector.user.id)
        await self.storage.delete_user_data(flow_connector.user.id)

        # Run the callbacks
        for callback in self._on_finish_callbacks:
            await callback(flow_connector)

    async def _create_user_and_channel(
        self, user: types.User | None = None, channel: types.Channel | types.DMChannel | None = None
    ):
        """Create the `User` and `Channel` records if they don't exist."""
        logger.info(f"Creating the User and Channel records for {user=}, {channel=}")

        user_id = getattr(user, "id", None) if user else None
        channel_id = getattr(channel, "id", None) if channel else None

        logger.debug(f"Creating the User and Channel records for {user_id=} and {channel_id=}")

        if user and not user_id:
            logger.warning(f"Failed to get the user ID: {user=}, {channel=}, {channel_id=}")

        if channel and not channel_id:
            logger.warning(f"Failed to get the channel ID: {channel=}, {user=}, {user_id=}")

        # Create the User record
        if user_id and not await self._storage__user_model.get_or_none(id=user_id):
            await self._storage__user_model.create(
                id=user_id,
                username=user.name,
                discriminator=user.discriminator,
                avatar=user.avatar.url if user.avatar else None,
            )
            logger.info(
                f"Created the User record for {user_id=}, "
                f"{getattr(user, 'name')=}, and {getattr(user, 'display_name')=}"
            )

        # Create the Channel record
        if channel_id and not await self._storage__channel_model.get_or_none(id=channel_id):
            await self._storage__channel_model.create(
                id=channel_id,
                name=getattr(channel, "name", None),
                guild_id=getattr(getattr(channel, "guild", None), "id", None),
                type=channel.type,
            )

            logger.info(
                f"Created the Channel record for {channel_id=}, "
                f"{getattr(channel, 'name', None)=}, {getattr(channel, 'type')=}"
            )

    # TODO: [2024-07-19 by Mykola] Use the decorators
    # @fail_safely
    async def _dispatch(self, flow_connector: FlowConnector) -> list[types.MessageToSend] | None:
        """Dispatch the flow."""
        # Create the User and Channel records if they don't exist
        await self._create_user_and_channel(flow_connector.user, flow_connector.channel)

        is_dm_channel = flow_connector.channel and flow_connector.channel.type == ChannelType.private

        if is_dm_channel:
            scope = FlowScopes.USER
        else:
            scope = FlowScopes.CHANNEL
        # TODO: [17.05.2024 by Mykola] Allow for `FlowScopes.GUILD` flows

        # Check whether this event has triggered any of the flows
        for flow in self.flows:
            # Check all the triggers
            if await flow.check_triggers(flow_connector, scope=scope):
                return await flow.run(flow_connector)
                # break

        else:
            # Check if it's not something that shouldn't be handled by the flows
            if (
                flow_connector.event == FlowConnectorEvents.MESSAGE
                and flow_connector.message.content
                and flow_connector.message.content.startswith(flow_connector.bot.command_prefix)
            ):
                if scope == FlowScopes.USER:
                    # Remove user's state, so that the user wouldn't resume any flow
                    await self.storage.delete_user_state(flow_connector.user.id)

                    raise EventCannotBeProcessed(
                        f"The message is a command that is not handled by any of the flows: "
                        f"{flow_connector.message.content}"
                    )
                else:
                    logger.warning(
                        "Out-of-scope `{scope}` command `{flow_connector.message.content}` is not handled by the flows",
                        scope=scope,
                        flow_connector=flow_connector,
                    )
                    raise EventCannotBeProcessed(
                        f"Out-of-scope `{scope}` command `{flow_connector.message.content}` is not handled by the flows"
                    )

            # Get all the flows that can be run:
            # Check if the flow can be run (maybe the user is in the middle of the flow)
            flows_that_can_be_run = [flow for flow in self.flows if await flow.check(flow_connector, scope=scope)]

            # If this event has not triggered any of the flows,
            # check if the user is in the middle of the flow, and if so, continue it

            # If there are multiple flows that can be run, decide which one gets the priority based on the scope
            if len(flows_that_can_be_run) > 1:
                flows_by_scope = defaultdict(list)
                for flow in flows_that_can_be_run:
                    # noinspection PyProtectedMember
                    flows_by_scope[flow._scope].append(flow)

                # If it's not a private channel, Channel-scoped flows get the priority
                if flow_connector.channel.type != types.ChannelType.private and (
                    channel_scope_flows := flows_by_scope.get(FlowScopes.CHANNEL)
                ):
                    flows_that_can_be_run = channel_scope_flows

            for flow in flows_that_can_be_run:
                try:
                    logger.info(f"Running the flow {flow} for {flow_connector.user.id}")
                    await flow.step(flow_connector)
                except FlowFinished:
                    # TODO: [28.08.2023 by Mykola] Go to the next flow?
                    return await self._finish_flow(flow_connector)

                # TODO: [16.03.2024 by Mykola] Maybe allow running multiple flows at the same time?
                break  # Do not allow running multiple flows at the same time
            else:
                if scope == FlowScopes.USER:
                    if flow_connector.event == FlowConnectorEvents.MESSAGE:
                        return await self._finish_flow(flow_connector)

                    logger.warning(f"Received an event that cannot be processed: {flow_connector.event}")
                    raise EventCannotBeProcessed(f"Received an event that cannot be processed: {flow_connector.event}")
                else:
                    logger.debug(
                        "Out-of-scope `{scope}` event cannot be processed: "
                        "`{flow_connector.event}` in `#{flow_connector.channel}`",
                        scope=scope,
                        flow_connector=flow_connector,
                    )
                    return  # Do not raise an exception, as it's not an error

    async def dispatch(self, flow_connector: FlowConnector) -> list[types.MessageToSend] | None:
        """Dispatch the flow."""
        # Set the current flow connector
        FlowConnector.set_current(flow_connector)

        async with self:
            return await self._dispatch(flow_connector)

    async def on_message(self, message: types.Message) -> list[Message] | None:
        """Handle the messages sent by the users."""

        # Save the message to the database
        message_obj: Message = await self.analytics_manager.get_or_save_message(message)

        # Ignore the messages sent by the bots
        if message.author.bot:
            return None

        # Get the user state and data
        # TODO: [20.08.2023 by Mykola] Use context manager for this
        logger.info(f"Getting the user state and data for {message.author.id}")
        user_state = await self._get_user_state(message.author)
        user_data = await self._get_user_data(message.author)

        # Get the channel state and data
        channel_state = await self._get_channel_state(message.channel)
        channel_data = await self._get_channel_data(message.channel)

        flow_connector = FlowConnector(
            flow_manager=self,
            bot=self.bot,
            event=FlowConnectorEvents.MESSAGE,
            user=message.author,
            channel=message.channel,
            message=message,
            message_obj=message_obj,
            user_state=user_state,
            user_data=user_data,
            channel_state=channel_state,
            channel_data=channel_data,
        )

        return await self.dispatch(flow_connector)

    async def on_interaction(self, interaction: types.Interaction):
        """Handle the interactions sent by the users."""
        # Save the interaction to the database
        interaction_obj, message_obj = await self.analytics_manager.save_interaction(
            interaction, return_message_obj=True
        )

        # Get the user state and data
        logger.info(f"Getting the user state and data for {interaction.user.id}")
        user_state = await self._get_user_state(interaction.user)
        user_data = await self._get_user_data(interaction.user)

        # Get the channel state and data
        channel_state = await self._get_channel_state(interaction.message.channel)
        channel_data = await self._get_channel_data(interaction.message.channel)

        # noinspection PyTypeChecker
        flow_connector = FlowConnector(
            flow_manager=self,
            bot=self.bot,
            event=FlowConnectorEvents.BUTTON_CLICK,
            user=interaction.user,
            channel=interaction.channel,
            user_state=user_state,
            user_data=user_data,
            message=interaction.message,
            interaction=interaction,
            message_obj=message_obj,
            interaction_obj=interaction_obj,
            channel_state=channel_state,
            channel_data=channel_data,
        )

        return await self.dispatch(flow_connector)

    async def on_member_join(self, member: types.Member):
        """Handle the `member_join` event."""
        # Save the user to the database
        await self.analytics_manager.save_new_member(member)

        # Get the user state and data
        logger.info(f"Getting the user state and data for {member.id}")
        # TODO: [22.08.2023 by Mykola] Use correct types here
        user_state = await self._get_user_state(member)
        user_data = await self._get_user_data(member)

        # noinspection PyProtectedMember
        flow_connector = FlowConnector(
            flow_manager=self,
            bot=self.bot,
            event=FlowConnectorEvents.MEMBER_JOIN,
            user=member._user,
            member=member,
            # TODO: [28.08.2023 by Mykola] Use the correct channel here
            channel=member.guild.system_channel,
            message=None,
            user_state=user_state,
            user_data=user_data,
            channel_state=None,
            channel_data=ChannelData(),
        )

        return await self.dispatch(flow_connector)

    async def on_member_update(self, before: types.Member, after: types.Member):
        """Handle the `member_update` event."""
        # Save the member update record to the database
        await self.analytics_manager.save_updated_member(before, after)

        # Get the user state and data
        logger.info(f"Getting the user state and data for {after.id}")
        user_state = await self._get_user_state(after)
        user_data = await self._get_user_data(after)

        # noinspection PyProtectedMember
        flow_connector = FlowConnector(
            flow_manager=self,
            bot=self.bot,
            event=FlowConnectorEvents.MEMBER_UPDATE,
            user=after._user,
            member=after,
            channel=after.guild.system_channel,
            message=None,
            user_state=user_state,
            user_data=user_data,
            extra_data={"old_member": before},
            channel_state=None,
            channel_data=ChannelData(),
        )

        return await self.dispatch(flow_connector)

    # region Context Manager
    async def __aenter__(self):
        """Enter the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        flow_connector = FlowConnector.get_current()

        # After the flow step(s) is/are run, update the user state and data
        if flow_connector.user:
            await self._set_user_state(flow_connector.user, flow_connector.user_state)
            await self._set_user_data(flow_connector.user, flow_connector.user_data)

        # Also, update the channel state and data
        if flow_connector.channel:
            await self._set_channel_state(flow_connector.channel, flow_connector.channel_state)
            await self._set_channel_data(flow_connector.channel, flow_connector.channel_data)

    # endregion


global_flow_manager = FlowManager(
    bot=global_bot,
)
