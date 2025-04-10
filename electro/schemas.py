from pydantic import BaseModel


class PlatformId(BaseModel):
    id: str


class Guild(BaseModel):
    platform_id: PlatformId
    name: str


class User(BaseModel):
    platform_id: PlatformId
    username: str
    guild: Guild | None


class Channel(BaseModel):
    platform_id: PlatformId
    name: str
    guild: Guild | None
    type: str


class ReceivedMessage(BaseModel):
    content: str
    author: User
    channel: Channel | None


class ButtonClick(BaseModel):
    id: int
    custom_id: str
    user: User
    channel: Channel | None
