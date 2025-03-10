import copy
import typing


class MemoryStorage:
    """
    In-memory based states storage.

    This type of storage is not recommended for usage in bots,
    because you will lose all states after restarting.
    """

    async def wait_closed(self):
        pass

    async def close(self):
        self.data.clear()

    def __init__(self):
        self.data = {}

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

    def resolve_address(self, chat, user):
        chat_id, user_id = map(str, self.check_address(chat=chat, user=user))

        if chat_id not in self.data:
            self.data[chat_id] = {}
        if user_id not in self.data[chat_id]:
            self.data[chat_id][user_id] = {"state": None, "data": {}, "bucket": {}}

        return chat_id, user_id

    async def get_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[str] = None,
    ) -> typing.Optional[str]:
        chat, user = self.resolve_address(chat=chat, user=user)
        return self.data[chat][user].get("state", default)

    async def get_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[str] = None,
    ) -> typing.Dict:
        chat, user = self.resolve_address(chat=chat, user=user)
        return copy.deepcopy(self.data[chat][user]["data"])

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
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["data"].update(data, **kwargs)

    async def set_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        state: typing.AnyStr = None,
    ):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["state"] = state

    async def set_data(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        data: typing.Dict = None,
    ):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["data"] = copy.deepcopy(data)
        self._cleanup(chat, user)

    async def reset_state(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        with_data: typing.Optional[bool] = True,
    ):
        await self.set_state(chat=chat, user=user, state=None)
        if with_data:
            await self.set_data(chat=chat, user=user, data={})
        self._cleanup(chat, user)

    @staticmethod
    def has_bucket():
        return True

    async def get_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[dict] = None,
    ) -> typing.Dict:
        chat, user = self.resolve_address(chat=chat, user=user)
        return copy.deepcopy(self.data[chat][user]["bucket"])

    async def set_bucket(
        self,
        *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        bucket: typing.Dict = None,
    ):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["bucket"] = copy.deepcopy(bucket)
        self._cleanup(chat, user)

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
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["bucket"].update(bucket, **kwargs)

    def _cleanup(self, chat, user):
        chat, user = self.resolve_address(chat=chat, user=user)
        if self.data[chat][user] == {"state": None, "data": {}, "bucket": {}}:
            del self.data[chat][user]
        if not self.data[chat]:
            del self.data[chat]
