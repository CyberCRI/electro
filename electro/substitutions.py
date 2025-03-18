"""The substitutions' module. Used to substitute the variables in all the `TemplatedString`s."""

from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from enum import Enum

import discord

from .flow_connector import FlowConnector
from .toolkit.redis_storage import RedisStorage

VALUE = typing.TypeVar("VALUE")


class BaseSubstitution(ABC, typing.Generic[VALUE]):
    """The base class for the substitution objects."""

    def __init__(
        self,
        default_value: typing.Optional[VALUE] = None,
        formatter: typing.Callable[[VALUE], str] | None = None,
        ensure_str_result: bool = False,
    ):
        self.default_value: VALUE = default_value
        self.formatter: typing.Callable[[VALUE], str] | None = formatter
        self.ensure_str_result: bool = ensure_str_result

    @abstractmethod
    async def _resolve(self, connector: FlowConnector) -> VALUE:
        """The method that should be implemented in the child classes."""
        raise NotImplementedError

    async def resolve(self, connector: FlowConnector) -> VALUE:
        """Resolve the value for the connector."""
        value = await self._resolve(connector) or self.default_value

        if self.formatter and value is not None:
            return self.formatter(value)
        else:
            return str(value) if self.ensure_str_result else value


class ManualRedisStorageSubstitution(BaseSubstitution):
    """The Substitution object that requests the data from the Redis storage."""

    redis_storage: RedisStorage
    redis_storage_key_name: str

    is_chat_specific: bool = False

    def __init__(
        self, redis_storage: RedisStorage, redis_storage_key_name: str, is_chat_specific: bool = False, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.redis_storage = redis_storage
        self.redis_storage_key_name = redis_storage_key_name
        self.is_chat_specific = is_chat_specific

    async def _resolve(self, connector: FlowConnector) -> str:
        if not self.is_chat_specific and not isinstance(connector.channel, discord.DMChannel):
            channel = await connector.user.create_dm()
        else:
            channel = connector.channel

        try:
            redis_user_data: dict[str, typing.Any] = (
                await self.redis_storage.get_data(
                    chat=channel.id,
                    user=connector.user.id,
                )
                or {}
            )
            data: VALUE = redis_user_data.get(self.redis_storage_key_name, self.default_value)
        except (TypeError, IndexError) as exception:
            return str(f"{exception} in REDIS STORAGE SUBSTITUTION for key: {self.redis_storage_key_name}")
        else:
            return data


class AttributeSubstitution(BaseSubstitution):
    substitution_object: BaseFlowSubstitutionObject
    attribute: str | None = None

    def __init__(self, substitution_object: BaseFlowSubstitutionObject, attribute: str | None = None, *args, **kwargs):
        """The Substitution object that would be fetched from the attribute of the object."""
        super().__init__(*args, **kwargs)

        self.substitution_object = substitution_object
        self.attribute = attribute

    async def _resolve(self, connector: FlowConnector) -> VALUE:
        if self.substitution_object.flow_connector_attribute:
            real_object = getattr(connector, self.substitution_object.flow_connector_attribute)
        else:
            # Should never happen, for now
            real_object = self.substitution_object.object

        if self.attribute:
            return getattr(real_object, self.attribute)
        else:
            return real_object


class CallbackSubstitution(BaseSubstitution[VALUE]):
    """The Substitution object that would be fetched from the callback."""

    callback: typing.Callable[[FlowConnector], typing.Awaitable[VALUE]]

    def __init__(self, callback: typing.Callable[[FlowConnector], typing.Awaitable[VALUE]], *args, **kwargs):
        """The Substitution object that would be fetched from the callback."""
        super().__init__(*args, **kwargs)

        self.callback = callback

    async def _resolve(self, connector: FlowConnector) -> VALUE:
        return await self.callback(connector)


class BaseFlowSubstitutionObject(ABC):
    object: object

    # TODO: [29.08.2023 by Mykola] Make it redundant to specify the attribute
    flow_connector_attribute: str | None = None

    def __getattribute__(self, item) -> AttributeSubstitution:
        try:
            return super().__getattribute__(item)
        except AttributeError:
            return AttributeSubstitution(self, item)


class UserSubstitutionObject(BaseFlowSubstitutionObject):
    object: discord.User

    flow_connector_attribute = "user"


UserObject = UserSubstitutionObject()


# region Specific Substitutions for Channels
class GlobalAbstractChannel(str, Enum):
    """The Enum for the global channels that are used in the bot."""

    DM_CHANNEL = "dm_channel"


async def resolve_channel(
    abstract_channel: GlobalAbstractChannel, user: discord.User
) -> discord.TextChannel | discord.DMChannel:
    """Resolve the channel by the name."""
    if abstract_channel == GlobalAbstractChannel.DM_CHANNEL:
        return await user.create_dm()

    raise ValueError(f"Unknown channel: {abstract_channel}")


# endregion
