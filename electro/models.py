"""The ORM models used in the `electro` Framework."""

from __future__ import annotations

from tortoise import fields
from tortoise.fields import ForeignKeyRelation

from .toolkit.images_storage.storages_enums import StoragesIDs
from .toolkit.tortoise_orm import Model


class BaseModel(Model):
    """The base model for all electro."""

    id = fields.IntField(pk=True)

    date_added = fields.DatetimeField(auto_now_add=True)
    date_updated = fields.DatetimeField(auto_now=True)

    is_active = fields.BooleanField(default=True)
    is_deleted = fields.BooleanField(default=False)

    date_deleted = fields.DatetimeField(null=True)

    class Meta:  # pylint: disable=too-few-public-methods
        """The metaclass for the base model."""

        abstract = True


# region Discord Models
class User(BaseModel):
    """The model for Discord User."""

    id = fields.BigIntField(pk=True)
    username = fields.CharField(max_length=255)

    discriminator = fields.IntField()
    avatar = fields.CharField(max_length=255, null=True)

    locale = fields.CharField(max_length=255, null=True)

    is_bot = fields.BooleanField(default=False)

    is_admin = fields.BooleanField(default=False)

    # guilds: fields.ManyToManyRelation["Guild"]  # TODO: [2024-08-30 by Mykola] Allow multiple guilds for the user.
    guild: fields.ForeignKeyRelation[Guild] | Guild = fields.ForeignKeyField(
        "electro.Guild", related_name="users", null=True
    )

    messages: fields.ReverseRelation[Message]
    state_changed: fields.ReverseRelation[UserStateChanged]

    files: fields.ReverseRelation[File]

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"{self.username}#{self.discriminator}"

    async def create_dm(self) -> Channel:
        """
        Create a DM channel with the user.
        """
        channel, _ = await Channel.get_or_create(id=self.id, defaults={"type": 1})
        return channel


class File(BaseModel):
    """The model for the file."""

    added_by_user: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", related_name="files", null=True)

    storage_service: StoragesIDs = fields.CharEnumField(StoragesIDs, max_length=32)

    storage_file_object_key = fields.TextField()

    file_name = fields.TextField(null=True)

    discord_attachment_id = fields.TextField(null=True)
    discord_cdn_url = fields.TextField(null=True)


class Guild(BaseModel):
    """The model for Discord Guild."""

    id = fields.BigIntField(pk=True)
    name = fields.CharField(max_length=255)

    icon = fields.CharField(max_length=255, null=True)
    banner = fields.CharField(max_length=255, null=True)
    description = fields.TextField(null=True)
    preferred_locale = fields.CharField(max_length=255, null=True)
    afk_channel_id = fields.BigIntField(null=True)
    afk_timeout = fields.IntField(null=True)
    owner_id = fields.BigIntField(null=True)

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return self.name


class GuildMember(BaseModel):
    """The model for Discord Guild Member."""

    user = fields.ForeignKeyField("electro.User", related_name="guild_members")
    guild = fields.ForeignKeyField("electro.Guild", related_name="guild_members")

    nickname = fields.CharField(max_length=255, null=True)
    joined_at = fields.DatetimeField(null=True)
    premium_since = fields.DatetimeField(null=True)
    deaf = fields.BooleanField(default=False)
    mute = fields.BooleanField(default=False)

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"{self.user} in {self.guild}"


class Channel(BaseModel):
    """The model for Discord Channel."""

    id = fields.BigIntField(pk=True)
    guild: Guild = fields.ForeignKeyField("electro.Guild", related_name="channels", null=True)

    name = fields.CharField(max_length=255, null=True)
    type = fields.CharField(max_length=255)

    used_for: str = fields.CharField(max_length=255, null=True)

    messages: fields.ReverseRelation[Message]

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"{self.name} in {self.guild or 'DM'} (used for {self.used_for})"


class Role(BaseModel):
    """The model for Discord Role."""

    id = fields.BigIntField(pk=True)

    guild: Guild = fields.ForeignKeyField("electro.Guild", related_name="roles")

    name = fields.CharField(max_length=255)
    color = fields.IntField(null=True)
    position = fields.IntField(null=True)
    permissions = fields.IntField(null=True)
    is_hoisted = fields.BooleanField(default=False)
    is_mentionable = fields.BooleanField(default=False)

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"{self.name} in {self.guild}"


# endregion Discord Models


# region Analytics models
class Message(BaseModel):
    """The model for Message."""

    id = fields.BigIntField(pk=True)

    author: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", related_name="messages")
    channel: ForeignKeyRelation[Channel] = fields.ForeignKeyField("electro.Channel", related_name="messages")

    content = fields.TextField()

    created_at = fields.DatetimeField()
    edited_at = fields.DatetimeField(null=True)

    is_pinned = fields.BooleanField(null=True)
    is_tts = fields.BooleanField(null=True)

    # Dynamically added fields
    is_bot_message = fields.BooleanField(null=True)
    is_command = fields.BooleanField(null=True)

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"`{self.author}` Message: `{self.content}`."


class Interaction(BaseModel):
    """The model for Interaction."""

    id = fields.BigIntField(pk=True)

    user: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", related_name="interactions")
    channel: ForeignKeyRelation[Channel] = fields.ForeignKeyField("electro.Channel", related_name="interactions")
    message: fields.ForeignKeyRelation[Message] = fields.ForeignKeyField("electro.Message", related_name="interactions")

    custom_id = fields.CharField(max_length=255)

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"`{self.user}` Interaction `{self.custom_id}`."


class UserStateChanged(BaseModel):
    """The model for User State Changed."""

    user: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", related_name="state_changed")

    previous_state = fields.TextField(null=True)
    new_state = fields.TextField()

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"`{self.user}` State Changed: `{self.previous_state}` -> `{self.new_state}`."


# endregion Analytics models


# region Base storage models
class BaseStorageModel(BaseModel):
    """The base model for storage models."""

    user: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", related_name=None, null=True)
    channel: ForeignKeyRelation[Channel] = fields.ForeignKeyField("electro.Channel", related_name=None, null=True)

    storage_models: list[type[BaseStorageModel]] = []

    def __init_subclass__(cls, **kwargs):
        """Initialize the subclass."""
        super().__init_subclass__(**kwargs)

        if cls in cls.storage_models or cls._meta.abstract:
            return

        cls.storage_models.append(cls)

    class Meta:  # pylint: disable=too-few-public-methods
        """The metaclass for the model."""

        abstract = True


class BaseImagesStepStorageModel(BaseStorageModel):
    """The base model for images step storage models."""

    buttons_sent_to_images = fields.JSONField(default=dict, null=True)
    images_sent_in_this_step = fields.JSONField(default=list, null=True)
    image_chosen = fields.CharField(max_length=255, null=True)
    # TODO: [2024-11-08 by Mykola] Add this later to maintain compatibility with the old data
    # TODO: [2024-11-08 by Mykola] Remove this from this model. It should be downstream
    # metaphors = fields.JSONField(default=list, null=True)

    load_more_button_custom_id = fields.CharField(max_length=255, null=True)

    class Meta:  # pylint: disable=too-few-public-methods
        """The metaclass for the model."""

        abstract = True


class BaseAssistantsStorageModel(BaseStorageModel):
    """The base model for OpenAI Assistants storage models."""

    thread_id = fields.CharField(max_length=255, null=True)

    class Meta:  # pylint: disable=too-few-public-methods
        """The metaclass for the model."""

        abstract = True


# endregion
