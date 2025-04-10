"""The module for `FlowBlock`. Apparently, it is not used in the project."""

from abc import ABC, ABCMeta
from dataclasses import dataclass

from .flow_connector import FlowConnector
from .flow_step import BaseFlowStep


class FlowBlockFinished(Exception):
    """The exception that is raised when the `FlowBlock` is finished."""


class FlowBlockMeta(ABCMeta):
    pass


class BaseFlowBlock(ABC, metaclass=FlowBlockMeta):
    """The base class for `FlowBlock`."""


@dataclass
class FlowBlock(BaseFlowBlock):
    """The class for `FlowBlock`."""

    steps: list[BaseFlowStep]

    async def run(self, connector: FlowConnector):
        """Run the `FlowBlock`."""
        if self.steps:
            return await self.steps[0].run(connector)

        raise FlowBlockFinished()

    async def process_response(self, connector: FlowConnector):
        """Process the response."""
        raise FlowBlockFinished()
