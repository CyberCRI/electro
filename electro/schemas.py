from abc import ABC
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import AssistantMessageDeltaType, AssistantType, FrontendAction


class AssistantSchema(BaseModel):
    """The schema for an assistant."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., title="The ID of the assistant")

    assistant_type: AssistantType = Field(..., title="The type of the assistant")

    date_added: datetime = Field(..., title="The date the assistant was added")
    date_updated: datetime = Field(..., title="The date the assistant was updated")


class AssistantChatThreadBaseSchema(BaseModel, ABC):
    """The base schema for an assistant's chat thread."""

    name: str | None = Field(None, title="The name of the chat thread")
    description: str | None = Field(None, title="The description of the chat thread")


class AssistantChatThreadCreateSchema(AssistantChatThreadBaseSchema):
    """The schema for creating an assistant's chat thread."""

    assistant_type: AssistantType = Field(..., title="The type of the Assistant to be used in the chat thread")


class AssistantChatThreadSchema(AssistantChatThreadBaseSchema):
    """The schema for an assistant's chat thread."""

    model_config = ConfigDict(from_attributes=True)

    assistant: AssistantSchema = Field(..., title="The assistant used in the chat thread")

    thread_id: str = Field(..., title="The ID of the chat thread")

    is_completed: bool = Field(..., title="Whether the chat thread is finished")

    date_added: datetime = Field(..., title="The date the chat thread was added")
    date_updated: datetime = Field(..., title="The date the chat thread was updated")


class AssistantChatMessageBaseSchema(BaseModel, ABC):
    """The base schema for an assistant's chat message."""

    role: str = Field(..., title="The role of the chat message")
    content: str = Field(..., title="The content of the chat message")


class AssistantChatMessageCreateSchema(AssistantChatMessageBaseSchema):
    """The schema for creating an assistant's chat message."""

    # The maximum length of the message _to create_ is set in the settings
    content: str = Field(
        ...,
        title="The content of the chat message to create",
    )


class AssistantChatMessageSchema(AssistantChatMessageBaseSchema):
    """The schema for an assistant's chat message."""

    model_config = ConfigDict(from_attributes=True)

    frontend_actions: list[FrontendAction] = Field([], title="The actions to be performed by the frontend")

    date_added: datetime = Field(..., title="The date the chat message was added")
    date_updated: datetime = Field(..., title="The date the chat message was updated")


class AssistantChatMessageDeltaSchema(AssistantChatMessageBaseSchema):
    """The schema for a delta of an assistant's chat message."""

    model_config = ConfigDict(from_attributes=True)

    message_id: str | None = Field(None, title="The ID of the chat message")

    type: AssistantMessageDeltaType = Field(..., title="The type of the delta")

    frontend_actions: list[FrontendAction] = Field([], title="The actions to be performed by the frontend")
