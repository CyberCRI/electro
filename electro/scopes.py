from enum import Enum


class FlowScopes(str, Enum):
    """The possible scopes for the Flow."""

    USER = "user"
    CHANNEL = "channel"
