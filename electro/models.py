"""The ORM models used in the `electro` Framework."""

from __future__ import annotations

from enum import Enum

from tortoise import fields
from tortoise.fields import ForeignKeyRelation, ManyToManyField

from .toolkit.files_storage.storages_enums import StoragesIDs
from .toolkit.tortoise_orm import Model


class BaseModel(Model):
    """The base model for all electro."""

    id = fields.IntField(pk=True)

    date_added = fields.DatetimeField(auto_now_add=True)
    date_updated = fields.DatetimeField(auto_now=True)

    is_active = fields.BooleanField(default=True)
    is_deleted = fields.BooleanField(default=False)
    date_deleted = fields.DatetimeField(null=True)

    class Meta:
        """The metaclass for the base model."""

        abstract = True


# region Core Models


class PlatformId(Model):
    """
    This model is used to store the IDs of the users, channels, and guilds on different platforms.

    It is used to link the users, channels, and guilds on different platforms to the same user, channel,
    or guild in the database.

    Attributes:
        id (int): The ID of the platform ID.
        type (str): The type of the platform ID. Can be "user", "channel", or "guild".
        platform_id (str): The ID of the user, channel, or guild on the platform.
        platform (str): The name of the platform.
        user (User): The user associated with the platform ID.
        channel (Channel): The channel associated with the platform ID.
        guild (Guild): The guild associated with the platform ID.
    """

    class PlatformIdTypes(str, Enum):
        """The types of platform IDs."""

        USER = "user"
        CHANNEL = "channel"
        GUILD = "guild"

    id = fields.IntField(pk=True)
    type = fields.CharField(max_length=255)
    platform_id = fields.CharField(max_length=255)
    platform = fields.CharField(max_length=255)
    user = fields.ForeignKeyField("electro.User", related_name="platform_ids", null=True)
    channel = fields.ForeignKeyField("electro.Channel", related_name="platform_ids", null=True)
    guild = fields.ForeignKeyField("electro.Guild", related_name="platform_ids", null=True)

    class Meta:
        unique_together = (("type", "platform_id", "platform"),)


class User(BaseModel):
    """The model for User."""

    id = fields.BigIntField(pk=True)
    username = fields.CharField(max_length=255)
    locale = fields.CharField(max_length=255, null=True)
    is_admin = fields.BooleanField(default=False)

    # guilds: fields.ManyToManyRelation["Guild"]  # TODO: [2024-08-30 by Mykola] Allow multiple guilds for the user.
    dm_channel: fields.ForeignKeyRelation[Channel] | Channel = fields.ForeignKeyField(
        "electro.Channel", related_name="dm_users", null=True
    )
    guild: fields.ForeignKeyRelation[Guild] | Guild = fields.ForeignKeyField(
        "electro.Guild", related_name="users", null=True
    )
    roles: fields.ManyToManyRelation[Role] = fields.ManyToManyField("electro.Role", related_name="users")

    platform_ids: fields.ReverseRelation[PlatformId]
    messages: fields.ReverseRelation[Message]
    state_changed: fields.ReverseRelation[UserStateChanged]
    files: fields.ReverseRelation[File]

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return self.username


class File(BaseModel):
    """The model for the file."""

    owner: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", null=True)
    content_type = fields.CharField(max_length=255, null=True)
    height = fields.IntField(null=True)
    width = fields.IntField(null=True)
    storage_service: StoragesIDs = fields.CharEnumField(StoragesIDs, max_length=32)
    storage_file_object_key = fields.TextField()
    file_name = fields.TextField(null=True)


class Guild(BaseModel):
    """The model for Guild."""

    id = fields.BigIntField(pk=True)
    name = fields.CharField(max_length=255)

    platform_ids: fields.ReverseRelation[PlatformId]

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return self.name


class Channel(BaseModel):
    """The model for Channel."""

    class ChannelTypes(str, Enum):
        """The types of channels."""

        DM = "dm"
        CHANNEL = "channel"

    class ChannelUsedFor(str, Enum):
        GLOBAL_ERRORS = "global_errors"
        MEANING_CARDS = "meaning_cards"
        CAUSE_CARDS = "cause_cards"
        IKIGAI_CARDS = "ikigai_cards"
        PROFESSION_CARDS = "profession_cards"

    id = fields.BigIntField(pk=True)
    guild: Guild = fields.ForeignKeyField("electro.Guild", related_name="channels", null=True)
    name = fields.CharField(max_length=255, null=True)
    type = fields.CharField(max_length=255)
    used_for = fields.CharEnumField(ChannelUsedFor, max_length=255, null=True)

    platform_ids: fields.ReverseRelation[PlatformId]
    messages: fields.ReverseRelation[Message]

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"Channel `{self.name}` in {self.guild}"


class Role(BaseModel):
    """The model for Role."""

    id = fields.BigIntField(pk=True)
    guild: Guild = fields.ForeignKeyField("electro.Guild", related_name="roles")
    name = fields.CharField(max_length=255)

    users: fields.ManyToManyRelation[User]

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"{self.name} in {self.guild}"


class Message(BaseModel):
    """The model for Message."""

    id = fields.BigIntField(pk=True)

    is_bot_message = fields.BooleanField(default=False)
    is_command = fields.BooleanField(default=False)
    is_temporary = fields.BooleanField(default=False)

    user: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", related_name="messages", null=True)
    channel: ForeignKeyRelation[Channel] = fields.ForeignKeyField("electro.Channel", related_name="messages", null=True)
    content = fields.TextField(null=True)
    caption = fields.TextField(null=True)
    files: fields.ManyToManyRelation[File] = ManyToManyField("electro.File", related_name="messages")
    static_files = fields.JSONField(default=list, null=True)
    buttons: fields.ReverseRelation[Button]

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"Message `{self.id}`."


class Button(BaseModel):
    """The model for Button."""

    id = fields.BigIntField(pk=True)
    custom_id = fields.CharField(max_length=255)
    style = fields.IntField()
    label = fields.CharField(max_length=255)
    clicked = fields.BooleanField(default=False)
    remove_after_click = fields.BooleanField(default=False)
    extra_data = fields.JSONField(null=True)
    message: ForeignKeyRelation[Message] = fields.ForeignKeyField("electro.Message", related_name="buttons", null=True)

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"Button `{self.id}`."


class UserStateChanged(BaseModel):
    """The model for User State Changed."""

    user: ForeignKeyRelation[User] = fields.ForeignKeyField("electro.User", related_name="state_changed")

    previous_state = fields.TextField(null=True)
    new_state = fields.TextField()

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"`{self.user}` State Changed: `{self.previous_state}` -> `{self.new_state}`."


# endregion Core Models


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

    class Meta:
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

    class Meta:
        """The metaclass for the model."""

        abstract = True


class BaseAssistantsStorageModel(BaseStorageModel):
    """The base model for OpenAI Assistants storage models."""

    thread_id = fields.CharField(max_length=255, null=True)

    class Meta:
        """The metaclass for the model."""

        abstract = True


# endregion
