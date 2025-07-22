"""
Base storage of the Framework. Needs to be improved.

Unlike the Storage Bucket, the Storage (this module) is the implementation of the internal storage for the framework.
It is used to store the state and data for the users.

You can think of it like this: if Storage Bucket is an SQL table, then Storage is the actual file on the disk.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Optional

from redis.asyncio import Redis

from .settings import settings

DEFAULT_FLOW_STORAGE_PREFIX = "flow"
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
    async def get_user_state(self, user_id: int, flow_code: str) -> str | None:
        """Get the state for a user."""
        raise NotImplementedError

    @abstractmethod
    async def get_channel_state(self, channel_id: int, flow_code: str) -> str | None:
        """Get the state for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def set_user_state(self, user_id: int, flow_code: str, state: str | None):
        """Set the state for a user."""
        raise NotImplementedError

    @abstractmethod
    async def set_channel_state(self, channel_id: int, flow_code: str, state: str | None):
        """Set the state for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def delete_user_state(self, user_id: int, flow_code: str):
        """Delete the state for a user."""
        raise NotImplementedError

    @abstractmethod
    async def delete_channel_state(self, channel_id: int, flow_code: str):
        """Delete the state for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def get_user_data(self, user_id: int, flow_code: str) -> UserData:
        """Get the data for a user."""
        raise NotImplementedError

    @abstractmethod
    async def get_channel_data(self, channel_id: int, flow_code: str) -> ChannelData:
        """Get the data for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def set_user_data(self, user_id: int, flow_code: str, data: UserData | dict[str, Any] | None):
        """Set the data for a user."""
        raise NotImplementedError

    @abstractmethod
    async def set_channel_data(self, channel_id: int, flow_code: str, data: ChannelData | dict[str, Any] | None):
        """Set the data for a channel."""
        raise NotImplementedError

    @abstractmethod
    async def delete_user_data(self, user_id: int, flow_code: str):
        """Delete the data for a user."""
        raise NotImplementedError

    @abstractmethod
    async def delete_channel_data(self, channel_id: int, flow_code: str):
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
        self._user_states: dict[str, str] = {}
        self._user_data: dict[str, UserData] = {}

        self._channel_states: dict[str, str] = {}
        self._channel_data: dict[str, ChannelData] = {}

    def _get_key(self, object_id: int, flow_code: str) -> str:
        """Get the key for the object."""
        return f"{flow_code}:{object_id}"

    async def get_user_state(self, user_id: int, flow_code: str) -> str | None:
        """Get the state for a user."""
        return self._user_states.get(self._get_key(user_id, flow_code))

    async def get_channel_state(self, channel_id: int, flow_code: str) -> str | None:
        """Get the state for a channel."""
        return self._channel_states.get(self._get_key(channel_id, flow_code))

    async def set_user_state(self, user_id: int, flow_code: str, state: str | None):
        """Set the state for a user."""
        self._user_states[self._get_key(user_id, flow_code)] = state

    async def set_channel_state(self, channel_id: int, flow_code: str, state: str | None):
        """Set the state for a channel."""
        self._channel_states[self._get_key(channel_id, flow_code)] = state

    async def delete_user_state(self, user_id: int, flow_code: str):
        """Delete the state for a user."""
        if self._get_key(user_id, flow_code) in self._user_states:
            del self._user_states[self._get_key(user_id, flow_code)]

    async def delete_channel_state(self, channel_id: int, flow_code: str):
        """Delete the state for a channel."""
        if self._get_key(channel_id, flow_code) in self._channel_states:
            del self._channel_states[self._get_key(channel_id, flow_code)]

    async def get_user_data(self, user_id: int, flow_code: str) -> UserData:
        """Get the data for a user."""
        if self._get_key(user_id, flow_code) not in self._user_data:
            self._user_data[self._get_key(user_id, flow_code)] = UserData()

        return self._user_data[self._get_key(user_id, flow_code)]

    async def get_channel_data(self, channel_id: int, flow_code: str) -> ChannelData:
        """Get the data for a channel."""
        if self._get_key(channel_id, flow_code) not in self._channel_data:
            self._channel_data[self._get_key(channel_id, flow_code)] = ChannelData()

        return self._channel_data[self._get_key(channel_id, flow_code)]

    async def set_user_data(self, user_id: int, flow_code: str, data: UserData | dict[str, Any] | None):
        """Set the data for a user."""
        self._user_data[self._get_key(user_id, flow_code)] = (
            data if isinstance(data, UserData) else UserData(**data) if data else UserData()
        )

    async def set_channel_data(self, channel_id: int, flow_code: str, data: ChannelData | dict[str, Any] | None):
        """Set the data for a channel."""
        self._channel_data[self._get_key(channel_id, flow_code)] = (
            data if isinstance(data, ChannelData) else ChannelData(**data) if data else ChannelData()
        )

    async def delete_user_data(self, user_id: int, flow_code: str):
        """Delete the data for a user."""
        if self._get_key(user_id, flow_code) in self._user_data:
            del self._user_data[self._get_key(user_id, flow_code)]

    async def delete_channel_data(self, channel_id: int, flow_code: str):
        """Delete the data for a channel."""
        if self._get_key(channel_id, flow_code) in self._channel_data:
            del self._channel_data[self._get_key(channel_id, flow_code)]

    async def clear(self):
        """Clear the storage."""
        self._user_states.clear()
        self._user_data.clear()
        self._channel_states.clear()
        self._channel_data.clear()


class FlowRedisStorage(BaseFlowStorage):
    """The storage used for `Flow`. Stores data for all the users in Redis."""

    def __init__(
        self,
        host: str = settings.REDIS_HOST,
        port: int = settings.REDIS_PORT,
        db: int = settings.REDIS_DB,
        password: Optional[str] = settings.REDIS_PASSWORD,
        prefix: str = DEFAULT_FLOW_STORAGE_PREFIX,
        state_ttl: Optional[int] = settings.FLOW_STORAGE_STATE_TTL,
        data_ttl: Optional[int] = settings.FLOW_STORAGE_DATA_TTL,
    ):
        self._redis = Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
        )
        self._prefix = prefix
        self._state_ttl = state_ttl
        self._data_ttl = data_ttl

    def _user_state_key(self, user_id: int, flow_code: str) -> str:
        return f"{self._prefix}:user:{user_id}:state:{flow_code}"

    def _user_data_key(self, user_id: int, flow_code: str) -> str:
        return f"{self._prefix}:user:{user_id}:data:{flow_code}"

    def _channel_state_key(self, channel_id: int, flow_code: str) -> str:
        return f"{self._prefix}:channel:{channel_id}:state:{flow_code}"

    def _channel_data_key(self, channel_id: int, flow_code: str) -> str:
        return f"{self._prefix}:channel:{channel_id}:data:{flow_code}"

    async def get_user_state(self, user_id: int, flow_code: str) -> str | None:
        return await self._redis.get(self._user_state_key(user_id, flow_code))

    async def get_channel_state(self, channel_id: int, flow_code: str) -> str | None:
        return await self._redis.get(self._channel_state_key(channel_id, flow_code))

    async def set_user_state(self, user_id: int, flow_code: str, state: str | None):
        key = self._user_state_key(user_id, flow_code)
        if state is None:
            await self._redis.delete(key)
        else:
            await self._redis.set(key, state, ex=self._state_ttl)

    async def set_channel_state(self, channel_id: int, flow_code: str, state: str | None):
        key = self._channel_state_key(channel_id, flow_code)
        if state is None:
            await self._redis.delete(key)
        else:
            await self._redis.set(key, state, ex=self._state_ttl)

    async def delete_user_state(self, user_id: int, flow_code: str):
        await self._redis.delete(self._user_state_key(user_id, flow_code))

    async def delete_channel_state(self, channel_id: int, flow_code: str):
        await self._redis.delete(self._channel_state_key(channel_id, flow_code))

    async def get_user_data(self, user_id: int, flow_code: str) -> UserData:
        raw = await self._redis.get(self._user_data_key(user_id, flow_code))
        return UserData(**json.loads(raw)) if raw else UserData()

    async def get_channel_data(self, channel_id: int, flow_code: str) -> ChannelData:
        raw = await self._redis.get(self._channel_data_key(channel_id, flow_code))
        return ChannelData(**json.loads(raw)) if raw else ChannelData()

    async def set_user_data(self, user_id: int, flow_code: str, data: UserData | dict[str, Any] | None):
        key = self._user_data_key(user_id, flow_code)
        if data:
            await self._redis.set(key, json.dumps(dict(data)), ex=self._data_ttl)
        else:
            await self._redis.delete(key)

    async def set_channel_data(self, channel_id: int, flow_code: str, data: ChannelData | dict[str, Any] | None):
        key = self._channel_data_key(channel_id, flow_code)
        if data:
            await self._redis.set(key, json.dumps(dict(data)), ex=self._data_ttl)
        else:
            await self._redis.delete(key)

    async def delete_user_data(self, user_id: int, flow_code: str):
        await self._redis.delete(self._user_data_key(user_id, flow_code))

    async def delete_channel_data(self, channel_id: int, flow_code: str):
        await self._redis.delete(self._channel_data_key(channel_id, flow_code))

    async def clear(self):
        # WARNING: This will delete all keys with the prefix!
        keys = []
        async for key in self._redis.scan_iter(f"{self._prefix}:*"):
            keys.append(key)
        if keys:
            await self._redis.delete(*keys)

    async def close(self):
        await self._redis.close()
