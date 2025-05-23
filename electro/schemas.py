from pydantic import BaseModel


class PlatformId(BaseModel):
    id: str


class Guild(BaseModel):
    platform_id: PlatformId
    name: str


class Channel(BaseModel):
    platform_id: PlatformId
    name: str
    guild: Guild | None
    type: str


class ReceivedMessage(BaseModel):
    content: str
    channel: Channel | None


class ButtonClick(BaseModel):
    id: int
    custom_id: str
    channel: Channel | None
