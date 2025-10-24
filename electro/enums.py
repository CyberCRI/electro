"""Different enums used in the project."""

from enum import Enum


class SupportedPlatforms(str, Enum):
    """The supported platforms for the project."""

    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    CUSTOM = "custom"


class ResponseTypes(str, Enum):
    """The actions that can be processed by the clients."""

    ERROR = "error"
    MESSAGE = "message"
    IMAGE = "image"
    START_TYPING = "start_typing"
    STOP_TYPING = "stop_typing"
    STOP_PROCESS = "stop_process"
    FINISH_FLOW = "finish_flow"
