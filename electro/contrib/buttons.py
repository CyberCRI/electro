"""The buttons that can be used in the `electro` Framework."""

import typing
from enum import Enum

from .. import types_ as types
from ..flow import Flow
from ..flow_connector import FlowConnector
from ..flow_step import BaseFlowStep

CALLBACK_TYPE = typing.Callable[[FlowConnector], typing.Awaitable[None]] | BaseFlowStep


class ButtonStyle(Enum):
    """A class to store the button styles."""

    primary = 1
    secondary = 2
    success = 3
    danger = 4

    def __int__(self):
        return self.value


class Button:
    """The base class for buttons."""

    def __init__(
        self,
        label: str | None = None,
        style: ButtonStyle = ButtonStyle.primary,
        custom_id: str | None = None,
        disabled: bool = False,
    ):
        super().__init__()
        if label and len(str(label)) > 80:
            raise ValueError("label must be 80 characters or fewer")
        if custom_id is not None and len(str(custom_id)) > 100:
            raise ValueError("custom_id must be 100 characters or fewer")
        if not isinstance(custom_id, str) and custom_id is not None:
            raise TypeError(
                f"expected custom_id to be str, not {custom_id.__class__.__name__}"
            )

        self.style = style
        self.label = label
        self.custom_id = custom_id
        self.disabled = disabled


class ActionButton(Button):
    """A button that performs an action when clicked."""

    action_callback: CALLBACK_TYPE

    def __init__(self, label: str, action_callback: CALLBACK_TYPE, *args, **kwargs):
        """Initialize the `ActionButton`."""
        super().__init__(label=label, *args, **kwargs)

        if isinstance(action_callback, BaseFlowStep):
            if action_callback.non_blocking:
                raise ValueError(
                    "Non-blocking steps cannot be used as action callbacks because 'non-blocking' would be ignored."
                )

        self.action_callback = action_callback

    async def trigger_action(self, flow_connector: FlowConnector):
        """Trigger the `ActionButton`."""
        if isinstance(self.action_callback, BaseFlowStep):
            await self.action_callback.run(flow_connector)
        else:
            await self.action_callback(flow_connector)


class GoToFlowButton(ActionButton):
    """A button that goes to a specific flow when clicked."""

    flow_name: str

    def __init__(self, label: str, flow_name: str, *args, **kwargs):
        """Initialize the `GoToFlowButton`."""
        super().__init__(label=label, action_callback=self.trigger_action, *args, **kwargs)

        self.flow_name = flow_name

    async def trigger_action(self, flow_connector: FlowConnector):
        """Trigger the `GoToFlowButton`."""
        flow: Flow | None = flow_connector.flow_manager.get_flow(self.flow_name)

        if not flow:
            raise ValueError(f"Flow with the name '{self.flow_name}' does not exist.")

        async with flow_connector.flow_manager:
            return await flow.run(flow_connector)


class DataButton(Button):
    def __init__(self, label: str, style: ButtonStyle, custom_id: str = None, **kwargs):
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.kwargs = kwargs

    async def callback(self, interaction: types.Interaction):
        interaction.data = {**interaction.data, **self.kwargs}
