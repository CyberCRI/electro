"""The buttons that can be used in the `electro` Framework."""

import typing
import uuid
from enum import Enum

from ..flow_connector import FlowConnector
from ..flow_step import BaseFlowStep, FlowStepDone

CALLBACK_TYPE = typing.Callable[[FlowConnector], typing.Awaitable[None]] | BaseFlowStep


class ButtonStyle(Enum):
    """A class to store the button styles."""

    primary = 1
    secondary = 2
    success = 3
    danger = 4

    blurple = 1
    grey = 2
    gray = 2
    green = 3
    red = 4
    url = 5

    def __int__(self):
        return self.value


class Button:
    """The base class for buttons."""

    def __init__(
        self,
        label: str | None = None,
        style: ButtonStyle = ButtonStyle.primary,
        disabled: bool = False,
        remove_after_click: bool = False,
    ):
        super().__init__()
        if label and len(str(label)) > 80:
            raise ValueError("label must be 80 characters or fewer")

        self.style = style
        self.label = label
        self.custom_id = str(uuid.uuid4())
        self.disabled = disabled
        self.remove_after_click = remove_after_click

    def to_dict(self) -> dict[str, typing.Any]:
        """Convert the button to a dictionary."""
        return {
            "style": int(self.style),
            "label": self.label,
            "custom_id": self.custom_id,
            "disabled": self.disabled,
            "remove_after_click": self.remove_after_click,
        }


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
        flow = flow_connector.flow_manager.get_flow(self.flow_name)

        if not flow:
            raise ValueError(f"Flow with the name '{self.flow_name}' does not exist.")

        async with flow_connector.flow_manager:
            return await flow.run(flow_connector)


class ConfirmButton(ActionButton):
    def __init__(
        self,
        label: str | None = None,
        style: ButtonStyle = ButtonStyle.primary,
        disabled: bool = False,
        remove_after_click: bool = True,
    ):
        super().__init__(
            label=label, style=style, action_callback=None, disabled=disabled, remove_after_click=remove_after_click
        )

    async def trigger_action(self, flow_connector: FlowConnector):
        raise FlowStepDone
