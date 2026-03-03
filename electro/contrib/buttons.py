"""The buttons that can be used in the `electro` Framework."""

import typing
import uuid
from abc import ABC
from enum import Enum

from ..flow_connector import FlowConnector
from ..flow_step import BaseFlowStep, FlowStepDone
from ..toolkit.i18n import TranslatedString

CALLBACK_TYPE = typing.Callable[[FlowConnector], typing.Awaitable[None]] | BaseFlowStep | None


class ButtonStyle(Enum):
    """A class to store the button styles."""

    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4

    BLURPLE = 1
    GREY = 2
    GRAY = 2
    GREEN = 3
    RED = 4
    URL = 5

    def __int__(self):
        return self.value


class BaseButton(ABC):
    """The base class for buttons."""

    def __init__(
        self,
        label: str | TranslatedString | None = None,
        style: ButtonStyle = ButtonStyle.PRIMARY,
        disabled: bool = False,
        remove_after_click: bool = False,
    ):
        if label and len(str(label)) > 80:
            raise ValueError("label must be 80 characters or fewer")

        self.style = style
        self.label = label
        self.custom_id = str(uuid.uuid4())
        self.disabled = disabled
        self.remove_after_click = remove_after_click


class DataButton(BaseButton):
    """A button that can store data."""

    def __init__(
        self,
        label: str | TranslatedString | None = None,
        style: ButtonStyle = ButtonStyle.PRIMARY,
        disabled: bool = False,
        remove_after_click: bool = False,
        **kwargs,
    ):
        super().__init__(label, style, disabled, remove_after_click)
        self.extra_data = kwargs


class ActionButton(BaseButton):
    """A button that performs an action when clicked."""

    action_callback: CALLBACK_TYPE

    def __init__(self, label: str, action_callback: CALLBACK_TYPE = None, **kwargs):
        """Initialize the `ActionButton`."""
        super().__init__(label=label, **kwargs)

        if isinstance(action_callback, BaseFlowStep):
            if action_callback.non_blocking:
                raise ValueError(
                    "Non-blocking steps cannot be used as action callbacks because 'non-blocking' would be ignored."
                )

        self.action_callback = action_callback

    async def trigger_action(self, flow_connector: FlowConnector):
        """Trigger the `ActionButton`."""
        if self.action_callback:
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
        label: str | TranslatedString | None = None,
        style: ButtonStyle = ButtonStyle.PRIMARY,
        disabled: bool = False,
        remove_after_click: bool = True,
    ):
        super().__init__(
            label=label, style=style, action_callback=None, disabled=disabled, remove_after_click=remove_after_click
        )

    async def trigger_action(self, flow_connector: FlowConnector):
        raise FlowStepDone
