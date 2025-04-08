"""Different enums used in the project."""

from enum import Enum


class SupportedPlatforms(str, Enum):
    """The supported platforms for the project."""

    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    CUSTOM = "custom"


class ResponseTypes(str, Enum):
    """The actions that can be processed by the clients."""

    MESSAGE = "message"
    IMAGE = "image"
    ADD_ROLE = "add_role"
    REMOVE_ROLE = "remove_role"
    START_TYPING = "start_typing"
    STOP_TYPING = "stop_typing"
