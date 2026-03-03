from pydantic import BaseModel


class PlatformId(BaseModel):
    id: str


class Channel(BaseModel):
    platform_id: PlatformId
    name: str
    type: str


class ReceivedMessage(BaseModel):
    content: str
    channel: Channel | None


class ButtonClick(BaseModel):
    id: int
    custom_id: str
    channel: Channel | None


class CookieToken(BaseModel):
    token: str | None = None
