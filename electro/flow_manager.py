"""Flow Manager, the main object that manages all the `Flow`s."""

from __future__ import annotations

import typing
from collections import defaultdict

from . import schemas
from ._common import ContextInstanceMixin
from .exceptions import DisabledButtonClick, EventCannotBeProcessed
from .flow import Flow, FlowConnector, FlowFinished
from .flow_connector import FlowConnectorEvents

# from decorators import fail_safely
from .models import Button, Channel, Guild, Message, PlatformId, User, UserStateChanged
from .scopes import FlowScopes
from .settings import settings
from .storage import BaseFlowStorage, ChannelData, FlowMemoryStorage, UserData
from .toolkit.loguru_logging import logger
from .toolkit.tortoise_orm import Model

if typing.TYPE_CHECKING:
    from .interfaces import BaseInterface


class AnalyticsManager(ContextInstanceMixin):
    """The object that manages the analytics."""

    def __init__(self, flow_manager: FlowManager):
        self.flow_manager = flow_manager

        # Set the current analytics manager
        self.set_current(self)

    @classmethod
    async def get_or_create_guild(cls, platform: str, guild_data: schemas.Guild) -> Guild:
        """Save the guild to the database."""
        platform_id, created = await PlatformId.get_or_create(
            platform_id=guild_data.platform_id.id, platform=platform, type=PlatformId.PlatformIdTypes.GUILD
        )
        if created:
            guild = await Guild.create(name=guild_data.name)
            platform_id.guild = guild
            logger.info(f"Created the Guild record for {guild.id=}, {guild.name=}")
            await platform_id.save()
        return await platform_id.guild

    @classmethod
    async def get_or_create_user(cls, platform: str, user_data: schemas.User) -> User:
        """Save the user to the database."""
        platform_id, created = await PlatformId.get_or_create(
            platform_id=user_data.platform_id.id, platform=platform, type=PlatformId.PlatformIdTypes.USER
        )
        if created:
            user = await User.create(username=user_data.username)
            platform_id.user = user
            logger.info(f"Created the User record for {user.id=}, {user.username=}")
            await platform_id.save()
        if user_data.guild:
            guild = await cls.get_or_create_guild(platform, user_data.guild)
            user.guild = guild
            await user.save()
        return await platform_id.user

    @classmethod
    async def get_or_create_channel(
        cls, platform: str, channel_data: schemas.Channel, user: typing.Optional[User] = None
    ) -> Channel:
        """Save the channel to the database."""
        platform_id, created = await PlatformId.get_or_create(
            platform_id=channel_data.platform_id.id, platform=platform, type=PlatformId.PlatformIdTypes.CHANNEL
        )
        if created:
            channel_type = channel_data.type
            if channel_type not in Channel.ChannelTypes:
                raise ValueError(f"Invalid channel type: {channel_type}")
            channel = await Channel.create(name=channel_data.name, type=channel_type)
            platform_id.channel = channel
            logger.info(f"Created the Channel record for {channel.id=}, {channel.name=}")
            await platform_id.save()
        if channel_data.guild:
            logger.error(f"{channel_data=}, {channel_data.guild=}")
            guild = await cls.get_or_create_guild(platform, channel_data.guild)
            channel.guild = guild
            await channel.save()
        channel = await platform_id.channel
        if user and channel.type == Channel.ChannelTypes.DM:
            if not user.dm_channel:
                user.dm_channel = channel
                await user.save()
                return channel
            if created:
                platform_id.channel = user.dm_channel
                await platform_id.save()
                await channel.delete()
                return await platform_id.channel
        return channel

    @classmethod
    async def save_message(cls, platform: str, message_data: schemas.ReceivedMessage) -> Message:
        """Save the message to the database."""
        author = await cls.get_or_create_user(platform, message_data.author)
        if message_data.channel:
            channel = await cls.get_or_create_channel(platform, message_data.channel, author)
        else:
            channel = None
        return await Message.create(
            is_command=message_data.content.startswith(settings.BOT_COMMAND_PREFIX),
            is_bot_message=False,
            user=author,
            content=message_data.content,
            channel=channel,
        )

    @classmethod
    async def save_button_click(cls, button_id: int) -> Button:
        """Save the button to the database."""
        # Get the user and channel objects (make sure they exist in the database
        button = await Button.get(id=button_id)
        if button.clicked and button.remove_after_click:
            raise DisabledButtonClick
        button.clicked = True
        await button.save()
        return button

    @classmethod
    async def save_user_state_changed(
        cls, user: User, previous_state: str | None, new_state: str | None
    ) -> UserStateChanged | None:
        """Save the user state changed record to the database."""
        if previous_state == new_state:
            return None
        return await UserStateChanged.create(user=user, previous_state=previous_state, new_state=new_state)


class FlowManager(ContextInstanceMixin):
    """The main object that manages all the `Flow`s."""

    _storage__user_model: Model = User
    _storage__channel_model: Model = Channel

    def __init__(
        self,
        flows: typing.Optional[list[Flow]] = None,
        storage: typing.Optional[BaseFlowStorage] = None,
        on_finish_callbacks: typing.Optional[list[typing.Callable[[FlowConnector], typing.Awaitable[None]]]] = None,
    ):
        self.flows: list[Flow] = flows or []

        self.storage = storage or FlowMemoryStorage()
        self.analytics_manager = AnalyticsManager(self)

        self._on_finish_callbacks: list[typing.Callable[[FlowConnector], typing.Awaitable[None]]] = (
            on_finish_callbacks or []
        )

        # Set the current flow manager
        self.set_current(self)

    # region User State and Data management
    async def _get_user_state(self, user: User) -> str | None:
        """Get the state of the user."""
        return await self.storage.get_user_state(user.id)

    async def _set_user_state(self, user: User, state: str | None):
        """Set the state of the user."""
        # Save the state to the database
        old_state = await self._get_user_state(user)
        if old_state != state:
            await self.analytics_manager.save_user_state_changed(user, old_state, state)
        await self.storage.set_user_state(user.id, state)

    async def _delete_user_state(self, user: User):
        """Delete the state of the user."""
        old_state = await self._get_user_state(user)
        if old_state:
            await self.analytics_manager.save_user_state_changed(user, old_state, None)
        await self.storage.delete_user_state(user.id)

    async def _get_user_data(self, user: User) -> UserData:
        """Get the data of the user."""
        return await self.storage.get_user_data(user.id)

    async def _set_user_data(self, user: User, data: UserData | dict[str, typing.Any] | None):
        """Set the data of the user."""
        await self.storage.set_user_data(user.id, data)

    async def _delete_user_data(self, user: User):
        """Delete the data of the user."""
        await self.storage.delete_user_data(user.id)

    # endregion

    # region Channel State and Data management
    async def _get_channel_state(self, channel: Channel) -> str | None:
        """Get the state of the channel."""
        return await self.storage.get_channel_state(channel.id)

    async def _set_channel_state(self, channel: Channel, state: str | None):
        """Set the state of the channel."""
        await self.storage.set_channel_state(channel.id, state)

    async def _delete_channel_state(self, channel: Channel):
        """Delete the state of the channel."""
        await self.storage.delete_channel_state(channel.id)

    async def _get_channel_data(self, channel: Channel) -> ChannelData:
        """Get the data of the channel."""
        return await self.storage.get_channel_data(channel.id)

    async def _set_channel_data(self, channel: Channel, data: ChannelData | dict[str, typing.Any] | None):
        """Set the data of the channel."""
        await self.storage.set_channel_data(channel.id, data)

    async def _delete_channel_data(self, channel: Channel):
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
        return

    # TODO: This is too complex and should be refactored.  pylint: disable=R0912
    # TODO: [2024-07-19 by Mykola] Use the decorators
    # @fail_safely
    async def _dispatch(self, flow_connector: FlowConnector):
        """Dispatch the flow."""

        # Create the User and Channel records if they don't exist
        if flow_connector.channel and flow_connector.channel.type == Channel.ChannelTypes.CHANNEL:
            scope = FlowScopes.CHANNEL
        else:
            scope = FlowScopes.USER
        # TODO: [17.05.2024 by Mykola] Allow for `FlowScopes.GUILD` flows

        # Check whether this event has triggered any of the flows
        for flow in self.flows:
            # Check all the triggers
            if await flow.check_triggers(flow_connector, scope=scope):
                await flow.run(flow_connector)
                break
        else:
            # Check if it's not something that shouldn't be handled by the flows
            if (
                flow_connector.event == FlowConnectorEvents.MESSAGE
                and flow_connector.message.content
                and flow_connector.message.content.startswith(settings.BOT_COMMAND_PREFIX)
            ):
                if scope == FlowScopes.USER:
                    # Remove user's state, so that the user wouldn't resume any flow
                    await self.storage.delete_user_state(flow_connector.user.id)

                    raise EventCannotBeProcessed(
                        f"The message is a command that is not handled by any of the flows: "
                        f"{flow_connector.message.content}"
                    )

                logger.warning(
                    f"Out-of-scope `{scope}` command `{flow_connector.message.content}` is not handled by the flows"
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
                    flows_by_scope[flow._scope].append(flow)  # pylint: disable=W0212

                # If it's not a private channel, Channel-scoped flows get the priority
                if flow_connector.channel.type == Channel.ChannelTypes.CHANNEL and (
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

                logger.debug(
                    "Out-of-scope `{scope}` event cannot be processed: "
                    "`{flow_connector.event}` in `#{flow_connector.channel}`",
                    scope=scope,
                    flow_connector=flow_connector,
                )
                return  # Do not raise an exception, as it's not an error

    async def dispatch(self, flow_connector: FlowConnector):
        """Dispatch the flow."""
        # Set the current flow connector
        FlowConnector.set_current(flow_connector)

        async with self:
            return await self._dispatch(flow_connector)

    async def on_message(self, platform: str, message_data: schemas.ReceivedMessage, interface: BaseInterface):
        """Handle the messages sent by the users."""

        # Save the message to the database
        message = await self.analytics_manager.save_message(platform, message_data)
        user = await message.user
        channel = await message.channel

        # Get the user state and data
        # TODO: [20.08.2023 by Mykola] Use context manager for this
        user_state = await self._get_user_state(user)
        user_data = await self._get_user_data(user)

        # Get the channel state and data
        if channel:
            channel_state = await self._get_channel_state(message.channel)
            channel_data = await self._get_channel_data(message.channel)
        else:
            channel_state = None
            channel_data = ChannelData()

        flow_connector = FlowConnector(
            flow_manager=self,
            event=FlowConnectorEvents.MESSAGE,
            user=user,
            channel=channel,
            message=message,
            user_state=user_state,
            user_data=user_data,
            channel_state=channel_state,
            channel_data=channel_data,
            interface=interface,
        )

        return await self.dispatch(flow_connector)

    async def on_button_click(self, platform: str, button_data: schemas.ButtonClick, interface: BaseInterface):
        """Handle the buttons clicked by the users."""
        # Save the button click to the database
        user = await self.analytics_manager.get_or_create_user(platform, button_data.user)
        channel = await self.analytics_manager.get_or_create_channel(platform, button_data.channel, user)
        try:
            button = await self.analytics_manager.save_button_click(button_data.id)
        except DisabledButtonClick:
            return await interface.send_message("button already clicked", user, channel)

        # Get the user state and data
        user_state = await self._get_user_state(user)
        user_data = await self._get_user_data(user)

        # Get the channel state and data
        channel_state = await self._get_channel_state(channel)
        channel_data = await self._get_channel_data(channel)

        # noinspection PyTypeChecker
        flow_connector = FlowConnector(
            flow_manager=self,
            event=FlowConnectorEvents.BUTTON_CLICK,
            user=user,
            channel=channel,
            button=button,
            user_state=user_state,
            user_data=user_data,
            channel_state=channel_state,
            channel_data=channel_data,
            interface=interface,
        )

        return await self.dispatch(flow_connector)

    # async def on_member_join(self, member: types.Member):
    #     """Handle the `member_join` event."""
    #     # Save the user to the database
    #     await self.analytics_manager.save_new_member(member)

    #     # Get the user state and data
    #     logger.info(f"Getting the user state and data for {member.id}")
    #     # TODO: [22.08.2023 by Mykola] Use correct types here
    #     user_state = await self._get_user_state(member)
    #     user_data = await self._get_user_data(member)

    #     # noinspection PyProtectedMember
    #     flow_connector = FlowConnector(
    #         flow_manager=self,
    #         event=FlowConnectorEvents.MEMBER_JOIN,
    #         user=member._user,
    #         member=member,
    #         # TODO: [28.08.2023 by Mykola] Use the correct channel here
    #         channel=member.guild.system_channel,
    #         message=None,
    #         user_state=user_state,
    #         user_data=user_data,
    #         channel_state=None,
    #         channel_data=ChannelData(),
    #     )

    #     return await self.dispatch(flow_connector)

    # async def on_member_update(self, before: types.Member, after: types.Member):
    #     """Handle the `member_update` event."""
    #     # Save the member update record to the database
    #     await self.analytics_manager.save_updated_member(before, after)

    #     # Get the user state and data
    #     logger.info(f"Getting the user state and data for {after.id}")
    #     user_state = await self._get_user_state(after)
    #     user_data = await self._get_user_data(after)

    #     # noinspection PyProtectedMember
    #     flow_connector = FlowConnector(
    #         flow_manager=self,
    #         event=FlowConnectorEvents.MEMBER_UPDATE,
    #         user=after._user,
    #         member=after,
    #         channel=after.guild.system_channel,
    #         message=None,
    #         user_state=user_state,
    #         user_data=user_data,
    #         extra_data={"old_member": before},
    #         channel_state=None,
    #         channel_data=ChannelData(),
    #     )

    #     return await self.dispatch(flow_connector)

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


global_flow_manager = FlowManager()
