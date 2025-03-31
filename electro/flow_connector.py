"""Flow Connector, the main object that is passed from one `Flow` to another."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

from ._common import ContextInstanceMixin
from .enums import SupportedPlatforms
from .interfaces import BaseInterface
from .models import Button, Channel, Message, User
from .storage import ChannelData, UserData

if TYPE_CHECKING:
    from electro import FlowManager


class FlowConnectorEvents(str, Enum):
    """The events that are used in the `FlowConnector`."""

    MESSAGE = "message"
    BUTTON_CLICK = "button_click"
    MEMBER_JOIN = "member_join"
    MEMBER_UPDATE = "member_update"


@dataclass
class FlowConnector(ContextInstanceMixin):
    """The connector that is passed from one `Flow` to another."""

    flow_manager: FlowManager
    interface: BaseInterface
    event: FlowConnectorEvents

    user_state: str | None
    user_data: UserData
    channel_state: str | None
    channel_data: ChannelData

    user: User
    channel: Channel
    message: Message | None = None
    button: Button | None = None

    substitutions: dict[str, str] | None = None
    extra_data: dict[str, Any] | None = None
