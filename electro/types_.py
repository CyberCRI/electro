"""The types (objects) used in the `electro` framework. Used to un-couple `electro` from the Discord framework."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .enums import ChannelType, SupportedPlatforms


class ElectroBaseModel(BaseModel):
    """The base model for all the models in the `electro` framework."""

    model_config = ConfigDict(extra="allow")

    # TODO: [2024-12-16 by Mykola] Allow more platforms
    from_platform: SupportedPlatforms = SupportedPlatforms.DISCORD


class User(ElectroBaseModel):
    """The model for User."""

    id: int
    username: str

    bot: bool = False

    discriminator: str | None
    avatar: dict | None


class Guild(ElectroBaseModel):
    """The model for Guild."""

    id: int
    name: str
    icon: str | None


class Channel(ElectroBaseModel):
    """The model for Channel."""

    id: int
    name: str | None
    type: ChannelType

    guild: Guild | None

    used_for: str | None


class Message(ElectroBaseModel):
    """The model for Message."""

    id: int
    content: str

    author: User
    channel: Channel

    created_at: datetime
    edited_at: datetime | None


class MessageToSend(ElectroBaseModel):
    """The model for Message to send."""

    content: str
    channel: Channel
