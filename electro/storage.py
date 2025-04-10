"""
Base storage of the Framework. Needs to be improved.

Unlike the Storage Bucket, the Storage (this module) is the implementation of the internal storage for the framework.
It is used to store the state and data for the users.

You can think of it like this: if Storage Bucket is an SQL table, then Storage is the actual file on the disk.
"""

from __future__ import annotations

import typing
from abc import ABC, abstractmethod

DEFAULT_FLOW_STORAGE_PREFIX = "flow::"
DEFAULT_MISSING_ADDRESS_PART = "missing"


class BaseData(dict):
    """The base class for the data."""


class UserData(BaseData):
    """The data for a user."""


class ChannelData(BaseData):
    """The data for a channel."""


class BaseFlowStorage(ABC):
    """The base class for the storage."""

    @abstractmethod
    async def get_user_state(self, user_id: int) -> str | None:
        """Get the state for a user."""
        raise NotImplementedError

    @abstractmethod
    async def get_channel_state(self, channel_id: int) -> str | None:
        """Get the state for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def set_user_state(self, user_id: int, state: str | None):
        """Set the state for a user."""
        raise NotImplementedError

    @abstractmethod
    async def set_channel_state(self, channel_id: int, state: str | None):
        """Set the state for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def delete_user_state(self, user_id: int):
        """Delete the state for a user."""
        raise NotImplementedError

    @abstractmethod
    async def delete_channel_state(self, channel_id: int):
        """Delete the state for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def get_user_data(self, user_id: int) -> UserData:
        """Get the data for a user."""
        raise NotImplementedError

    @abstractmethod
    async def get_channel_data(self, channel_id: int) -> ChannelData:
        """Get the data for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def set_user_data(self, user_id: int, data: UserData | dict[str, typing.Any] | None):
        """Set the data for a user."""
        raise NotImplementedError

    @abstractmethod
    async def set_channel_data(self, channel_id: int, data: ChannelData | dict[str, typing.Any] | None):
        """Set the data for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def delete_user_data(self, user_id: int):
        """Delete the data for a user."""
        raise NotImplementedError

    @abstractmethod
    async def delete_channel_data(self, channel_id: int):
        """Delete the data for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def clear(self):
        """Clear the storage."""
        raise NotImplementedError


# TODO: [29.08.2023 by Mykola] Improve the storage
class FlowMemoryStorage(BaseFlowStorage):
    """The storage used for `Flow`. Stores data for all the users."""

    def __init__(self):
        self._user_states: dict[int, str] = {}
        self._user_data: dict[int, UserData] = {}

        self._channel_states: dict[int, str] = {}
        self._channel_data: dict[int, ChannelData] = {}

    async def get_user_state(self, user_id: int) -> str | None:
        """Get the state for a user."""
        return self._user_states.get(user_id)

    async def get_channel_state(self, channel_id: int) -> str | None:
        """Get the state for a channel."""
        return self._channel_states.get(channel_id)

    async def set_user_state(self, user_id: int, state: str | None):
        """Set the state for a user."""
        self._user_states[user_id] = state

    async def set_channel_state(self, channel_id: int, state: str | None):
        """Set the state for a channel."""
        self._channel_states[channel_id] = state

    async def delete_user_state(self, user_id: int):
        """Delete the state for a user."""
        if user_id in self._user_states:
            del self._user_states[user_id]

    async def delete_channel_state(self, channel_id: int):
        """Delete the state for a channel."""
        if channel_id in self._channel_states:
            del self._channel_states[channel_id]

    async def get_user_data(self, user_id: int) -> UserData:
        """Get the data for a user."""
        if user_id not in self._user_data:
            self._user_data[user_id] = UserData()

        return self._user_data[user_id]

    async def get_channel_data(self, channel_id: int) -> ChannelData:
        """Get the data for a channel."""
        if channel_id not in self._channel_data:
            self._channel_data[channel_id] = ChannelData()

        return self._channel_data[channel_id]

    async def set_user_data(self, user_id: int, data: UserData | dict[str, typing.Any] | None):
        """Set the data for a user."""
        self._user_data[user_id] = data if isinstance(data, UserData) else UserData(**data) if data else UserData()

    async def set_channel_data(self, channel_id: int, data: ChannelData | dict[str, typing.Any] | None):
        """Set the data for a channel."""
        self._channel_data[channel_id] = (
            data if isinstance(data, ChannelData) else ChannelData(**data) if data else ChannelData()
        )

    async def delete_user_data(self, user_id: int):
        """Delete the data for a user."""
        if user_id in self._user_data:
            del self._user_data[user_id]

    async def delete_channel_data(self, channel_id: int):
        """Delete the data for a channel."""
        if channel_id in self._channel_data:
            del self._channel_data[channel_id]

    async def clear(self):
        """Clear the storage."""
        self._user_states.clear()
        self._user_data.clear()
        self._channel_states.clear()
        self._channel_data.clear()
