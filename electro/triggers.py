"""The module for `Trigger`s used with the Framework."""

from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .flow_connector import FlowConnectorEvents
from .scopes import FlowScopes
from .settings import settings

if typing.TYPE_CHECKING:
    from .flow import FlowConnector


class BaseFlowTrigger(ABC):
    """The base class for `FlowTrigger`."""

    allowed_scopes: list[FlowScopes] = [FlowScopes.USER]

    # noinspection PyUnusedLocal
    async def check_scope(self, connector: FlowConnector, scope: FlowScopes | None = None) -> bool:
        """Check if the `Flow` can be run based on the scope."""
        if scope and scope not in self.allowed_scopes:
            return False
        return True

    @abstractmethod
    async def _check(self, connector: FlowConnector, scope: FlowScopes | None = None) -> bool:
        """Check if the `Flow` can be run."""
        raise NotImplementedError

    async def check(self, connector: FlowConnector, scope: FlowScopes | None = None) -> bool:
        """Check if the `Flow` can be run based on the scope and the trigger."""
        return await self.check_scope(connector, scope) and await self._check(connector, scope)


@dataclass
class CommandTrigger(BaseFlowTrigger):
    """The trigger that is activated when a command is run."""

    command: str
    allowed_scopes: list[FlowScopes] = field(default_factory=lambda: BaseFlowTrigger.allowed_scopes)

    async def _check(self, connector: FlowConnector, scope: FlowScopes | None = None) -> bool:
        """Check if the `Flow` can be run based on the command (and the scope, if provided)."""
        matches: list[str] = [
            f"{settings.BOT_COMMAND_PREFIX}{self.command}",
        ]

        if settings.DO_USE_COMMAND_ALIASES or settings.DEBUG:
            command_alias = "".join([part[0] for part in self.command.split("_") if part])
            matches.append(f"{settings.BOT_COMMAND_PREFIX}{command_alias}")

        if connector.message and connector.message.content in matches:
            return True


class BaseEventTrigger(BaseFlowTrigger):
    """The base class for event triggers."""

    event: str

    @property
    @abstractmethod
    def event(self) -> str:
        """The event that activates the trigger."""
        raise NotImplementedError

    async def check_scope(self, connector: FlowConnector, scope: FlowScopes | None = None) -> bool:
        """Check if the `Flow` can be run based on the scope."""
        # Allow the `Flow` to run for any scope
        return True

    async def _check(self, connector: FlowConnector, *_, **__) -> bool:
        """Check if the `Flow` can be run based on the event."""
        if connector.event == self.event:
            return True


class MemberJoinedTrigger(BaseEventTrigger):
    """The trigger that is activated when a member joins the server."""

    event: FlowConnectorEvents = FlowConnectorEvents.MEMBER_JOIN


class MemberUpdatedTrigger(BaseEventTrigger):
    """The trigger that is activated when a member is updated."""

    event: FlowConnectorEvents = FlowConnectorEvents.MEMBER_UPDATE
