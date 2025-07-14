"""Different enums used in the project."""

from enum import Enum


class SupportedPlatforms(str, Enum):
    """The supported platforms for the project."""

    DISCORD = "discord"
    # WHATSAPP = "whatsapp"
    # TELEGRAM = "telegram"
    # SLACK = "slack"


class ChannelType(Enum):
    """Channel type"""

    text = 0
    private = 1
    voice = 2
    group = 3
    category = 4
    news = 5
    news_thread = 10
    public_thread = 11
    private_thread = 12
    stage_voice = 13
    directory = 14
    forum = 15

    def __str__(self):
        return self.name


# region Real-time Assistant Messages (using SSE)
class AssistantMessageDeltaType(str, Enum):
    """The types of deltas for an assistant's chat message."""

    MESSAGE_START = "message_start"
    MESSAGE_END = "message_end"

    METADATA = "metadata"

    CONTENT_BLOCK = "content_block"

    ERROR = "error"


class AssistantType(str, Enum):
    """The Assistant types."""

    CONVERSATIONAL = "conversational"


class FrontendAction(str, Enum):
    """The Front-end actions."""

    ADD_SPARKLES = "add_sparkles"
    ADD_BALLOONS = "add_balloons"


# endregion
