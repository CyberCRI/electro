"""Different enums used in the project."""

from enum import Enum


class SupportedPlatforms(str, Enum):
    """The supported platforms for the project."""

    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    CUSTOM = "custom"
