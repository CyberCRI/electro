"""
The module that provides the `RedisStorage` storage for the bot.

It uses the `REDIS_URL` environment variable to connect to the Redis server.
"""

import asyncio
import json
import typing

import dj_redis_url
from redis.asyncio.client import Redis

from ..settings import settings

if not (redis_url := settings.REDIS_URL):
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

redis_config: dict = dj_redis_url.config(default=str(redis_url))

STATE_KEY = "state"
STATE_DATA_KEY = "data"
STATE_BUCKET_KEY = "bucket"


def parse_config(config_to_parse: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """
    Parse `redis_config` for `RedisStorage` by `.lower()`ing the keys.

    Structure of `redis_config`:
        >>> redis_config.keys()
        dict_keys(['DB', 'PASSWORD', 'HOST', 'PORT'])
    """
    return dict((k.lower(), v) for k, v in config_to_parse.items())


class BaseStorage:
    """
    You are able to save current user's state
    and data for all steps in states-storage
    """

    async def close(self):
        """
        You have to override this method and use when application shutdowns.
        Perhaps you would like to save data and etc.

        :return:
        """
        raise NotImplementedError

    async def wait_closed(self):
        """
        You have to override this method for all asynchronous storages (e.g., Redis).

        :return:
        """
        raise NotImplementedError

    @classmethod
    def check_address(
        cls,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
    ) -> typing.Tuple[typing.Union[str, int]]:
        """
        In all storage's methods chat or user is always required.
        If one of them is not provided, you have to set missing value based on the provided one.

        This method performs the check described above.

        :param chat: chat_id
        :param user: user_id
        :return:
        """
        if chat is None and user is None:
            raise ValueError("`user` or `chat` parameter is required but no one is provided!")

        if user is None:
            user = chat

        elif chat is None:
            chat = user

        return chat, user

    async def get_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[str] = None,
    ) -> typing.Optional[str]:
        """
        Get current state of user in chat. Return `default` if no record is found.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :param default:
        :return:
        """
        raise NotImplementedError

    async def get_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[typing.Dict] = None,
    ) -> typing.Dict:
        """
        Get state-data for user in chat. Return `default` if no data is provided in storage.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :param default:
        :return:
        """
        raise NotImplementedError

    async def set_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        state: typing.Optional[typing.AnyStr] = None,
    ):
        """
        Set new state for user in chat

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :param state:
        """
        raise NotImplementedError

    async def set_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        data: typing.Dict = None,
    ):
        """
        Set data for user in chat

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :param data:
        """
        raise NotImplementedError

    async def update_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        data: typing.Dict = None,
        **kwargs,
    ):
        """
        Update data for user in chat

        You can use data parameter or|and kwargs.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param data:
        :param chat:
        :param user:
        :param kwargs:
        :return:
        """
        raise NotImplementedError

    async def reset_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
    ):
        """
        Reset data for user in chat.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :return:
        """
        await self.set_data(chat=chat, user=user, data={})

    async def reset_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        with_data: typing.Optional[bool] = True,
    ):
        """
        Reset state for user in chat.
        You may desire to use this method when finishing conversations.

        Chat or user is always required. If one of this is not presented,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :param with_data:
        :return:
        """
        chat, user = self.check_address(chat=chat, user=user)
        await self.set_state(chat=chat, user=user, state=None)
        if with_data:
            await self.set_data(chat=chat, user=user, data={})

    async def finish(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
    ):
        """
        Finish conversation for user in chat.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :return:
        """
        await self.reset_state(chat=chat, user=user, with_data=True)

    def has_bucket(self):
        return False

    async def get_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[dict] = None,
    ) -> typing.Dict:
        """
        Get bucket for user in chat. Return `default` if no data is provided in storage.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :param default:
        :return:
        """
        raise NotImplementedError

    async def set_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        bucket: typing.Dict = None,
    ):
        """
        Set bucket for user in chat

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :param bucket:
        """
        raise NotImplementedError

    async def update_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        bucket: typing.Dict = None,
        **kwargs,
    ):
        """
        Update bucket for user in chat

        You can use bucket parameter or|and kwargs.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param bucket:
        :param chat:
        :param user:
        :param kwargs:
        :return:
        """
        raise NotImplementedError

    async def reset_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
    ):
        """
        Reset bucket dor user in chat.

        Chat or user is always required. If one of them is not provided,
        you have to set missing value based on the provided one.

        :param chat:
        :param user:
        :return:
        """
        await self.set_bucket(chat=chat, user=user, bucket={})

    @staticmethod
    def resolve_state(value):
        if value is None:
            return

        if isinstance(value, str):
            return value

        return str(value)


class RedisStorage(BaseStorage):
    """
    Busted Redis-base storage for FSM.
    Works with Redis connection pool and customizable keys prefix.

    Usage:

    .. code-block:: python3

        storage = RedisStorage('localhost', 6379, db=5, pool_size=10, prefix='my_fsm_key')
        dp = Dispatcher(bot, storage=storage)

    And need to close Redis connection when shutdown

    .. code-block:: python3

        await dp.storage.close()

    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: typing.Optional[int] = None,
        password: typing.Optional[str] = None,
        ssl: typing.Optional[bool] = None,
        pool_size: int = 10,
        loop: typing.Optional[asyncio.AbstractEventLoop] = None,
        prefix: str = "fsm",
        state_ttl: typing.Optional[int] = None,
        data_ttl: typing.Optional[int] = None,
        bucket_ttl: typing.Optional[int] = None,
        **kwargs,
    ):
        self._redis: typing.Optional[Redis] = Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
            max_connections=pool_size,
            decode_responses=True,
            **kwargs,
        )

        self._prefix = (prefix,)
        self._state_ttl = state_ttl
        self._data_ttl = data_ttl
        self._bucket_ttl = bucket_ttl

    def generate_key(self, *parts):
        return ":".join(self._prefix + tuple(map(str, parts)))

    async def close(self):
        await self._redis.close()

    async def wait_closed(self):
        pass

    async def get_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[str] = None,
    ) -> typing.Optional[str]:
        chat, user = self.check_address(chat=chat, user=user)
        key = self.generate_key(chat, user, STATE_KEY)
        return await self._redis.get(key) or self.resolve_state(default)

    async def get_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[dict] = None,
    ) -> typing.Dict:
        chat, user = self.check_address(chat=chat, user=user)
        key = self.generate_key(chat, user, STATE_DATA_KEY)
        raw_result = await self._redis.get(key)
        if raw_result:
            return json.loads(raw_result)
        return default or {}

    async def set_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        state: typing.Optional[typing.AnyStr] = None,
    ):
        chat, user = self.check_address(chat=chat, user=user)
        key = self.generate_key(chat, user, STATE_KEY)
        if state is None:
            await self._redis.delete(key)
        else:
            await self._redis.set(key, self.resolve_state(state), ex=self._state_ttl)

    async def set_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        data: typing.Dict = None,
    ):
        chat, user = self.check_address(chat=chat, user=user)
        key = self.generate_key(chat, user, STATE_DATA_KEY)
        if data:
            await self._redis.set(key, json.dumps(data), ex=self._data_ttl)
        else:
            await self._redis.delete(key)

    async def update_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        data: typing.Dict = None,
        **kwargs,
    ):
        if data is None:
            data = {}
        temp_data = await self.get_data(chat=chat, user=user, default={})
        temp_data.update(data, **kwargs)
        await self.set_data(chat=chat, user=user, data=temp_data)

    def has_bucket(self):
        return True

    async def get_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[dict] = None,
    ) -> typing.Dict:
        chat, user = self.check_address(chat=chat, user=user)
        key = self.generate_key(chat, user, STATE_BUCKET_KEY)
        raw_result = await self._redis.get(key)
        if raw_result:
            return json.loads(raw_result)
        return default or {}

    async def set_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        bucket: typing.Dict = None,
    ):
        chat, user = self.check_address(chat=chat, user=user)
        key = self.generate_key(chat, user, STATE_BUCKET_KEY)
        if bucket:
            await self._redis.set(key, json.dumps(bucket), ex=self._bucket_ttl)
        else:
            await self._redis.delete(key)

    async def update_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        bucket: typing.Dict = None,
        **kwargs,
    ):
        if bucket is None:
            bucket = {}
        temp_bucket = await self.get_bucket(chat=chat, user=user)
        temp_bucket.update(bucket, **kwargs)
        await self.set_bucket(chat=chat, user=user, bucket=temp_bucket)

    async def reset_all(self, full=True):
        """
        Reset states in DB

        :param full: clean DB or clean only states
        :return:
        """
        if full:
            await self._redis.flushdb()
        else:
            keys = await self._redis.keys(self.generate_key("*"))
            await self._redis.delete(*keys)

    async def get_states_list(self) -> typing.List[typing.Tuple[str, str]]:
        """
        Get list of all stored chat's and user's

        :return: list of tuples where first element is chat id and second is user id
        """
        result = []

        keys = await self._redis.keys(self.generate_key("*", "*", STATE_KEY))
        for item in keys:
            *_, chat, user, _ = item.split(":")
            result.append((chat, user))

        return result


# According to the structure above, it's better to write this expression
redis_storage = RedisStorage(
    **parse_config(redis_config),
    # Configs below are from here:
    #  https://devcenter.heroku.com/articles/ah-redis-stackhero#:~:text=The%20error%20%E2%80%9Credis.,and%20the%20connection%20closes%20automatically.
    health_check_interval=10,
    socket_connect_timeout=5,
    retry_on_timeout=True,
    socket_keepalive=True,
)
