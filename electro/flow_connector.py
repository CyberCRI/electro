"""Flow Connector, the main object that is passed from one `Flow` to another."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

import discord
from discord.ext import commands

from ._common import ContextInstanceMixin
from .interfaces import Interface
from .models import Interaction, Message
from .storage import ChannelData, UserData
from .types_ import Channel, User

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

    # TODO: [05.09.2023 by Mykola] Forbid re-assigning the attributes of this class

    flow_manager: FlowManager

    bot: commands.Bot

    event: FlowConnectorEvents

    user: User | None
    channel: Channel | None

    user_state: str | None
    user_data: UserData

    channel_state: str | None
    channel_data: ChannelData

    message: discord.Message | None = None
    interaction: discord.Interaction | None = None

    message_obj: Message | None = None
    interaction_obj: Interaction | None = None

    member: discord.Member | None = None
    substitutions: dict[str, str] | None = None

    extra_data: dict[str, Any] | None = None

    interface: Interface | None = None
