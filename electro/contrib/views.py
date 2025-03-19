"""The module with extra Views that can be used with the Framework."""

from __future__ import annotations

import inspect
import typing
from abc import ABC, abstractmethod
from copy import copy

import discord

# noinspection PyProtectedMember
from discord.ui.view import _ViewWeights
from tenacity import retry, stop_after_attempt, wait_fixed

from ..substitutions import BaseSubstitution
from ..contrib.buttons import Button, ButtonStyle
from ..toolkit.loguru_logging import logger

if typing.TYPE_CHECKING:
    from .buttons import ActionButton

from .storage_buckets import StorageBucketElement

if typing.TYPE_CHECKING:
    from ..flow_connector import FlowConnector


LAST_ROW_INDEX = 4


class ViewStepFinished(Exception):
    """The exception that is raised when the `View` is finished."""

    pass


class BaseView(discord.ui.View, ABC):
    """The base view for all the views in the framework."""

    # NB: The use of `emoji_buttons` is discouraged unless the button's label is a one-time text
    # (not being saved in the storage)
    emoji_buttons: bool = False
    buttons_style: ButtonStyle = ButtonStyle.primary

    _parent_view: BaseView | None = None
    _custom_id_to_button: dict[str, Button] = {}

    _user_connectors_to_views: dict[int, BaseView]

    _trim_button_labels_at: int = 80

    def __init__(
        self,
        emoji_buttons: bool | None = None,
        buttons_style: ButtonStyle = ButtonStyle.primary,
        force_init_on_step_run: bool = False,
        clear_storage_on_step_run: bool = False,
        timeout: int | None = None,
    ):
        """Initialize the view."""
        self.emoji_buttons = emoji_buttons if emoji_buttons is not None else self.emoji_buttons
        self.buttons_style = buttons_style or self.buttons_style

        self.force_init_on_step_run = force_init_on_step_run
        self.clear_storage_on_step_run = clear_storage_on_step_run

        self._user_connectors_to_views = {}

        super().__init__(timeout=timeout)

    async def _on_view_created(self, flow_connector: FlowConnector, view: BaseView):
        """The method that is called when the view is created."""
        pass

    async def get_or_create_for_connector(
        self,
        flow_connector: FlowConnector,
        dynamic_buttons: list[str | Button] | None = None,
        force_init: bool = False,
        force_get: bool = False,
        from_step_run: bool = False,
    ) -> typing.Self:
        """Get the view specifically for this `FlowConnector`."""
        if from_step_run:
            force_init = force_init or self.force_init_on_step_run

        if self.clear_storage_on_step_run and from_step_run:
            if isinstance(self, StorageMixin):
                await self.clear_storage()

        if force_get and force_init:
            raise ValueError("Cannot force both get and init.")

        if not force_init and (view := self._user_connectors_to_views.get(flow_connector.user.id)):
            return view

        if force_get:
            raise ValueError("Cannot force get if the view is not initialized.")

        view = copy(self)
        # Since we're _copying_ the view, the `.children` attribute would be copied as well, as a
        # link to the original view's children. We need to set it to an empty list to avoid
        # modifying the original view's children
        view.children = []
        # Same with `self.__weights = _ViewWeights(self.children)`
        view._View__weights = _ViewWeights(view.children)

        static_buttons: list[Button | str] = [
            (
                button_or_string[: self._trim_button_labels_at]
                if self._trim_button_labels_at and isinstance(button_or_string, str)
                else button_or_string
            )
            for button_or_string in await self.get_static_buttons(flow_connector)
        ]

        # Add the new buttons to the view
        view._add_buttons(*dynamic_buttons or [], *static_buttons)

        # Add the buttons to the `_custom_id_to_button` dict
        # This is used so that we can get the button by its custom id when we process the
        # interaction
        # TODO: [07.09.2023 by Mykola] Find a more sustainable way to do this
        for item in view.children:
            if isinstance(item, Button):
                self._custom_id_to_button[item.custom_id] = item

        view._parent_view = self

        # Save the view for the user
        self._user_connectors_to_views[flow_connector.user.id] = view

        await self._on_view_created(flow_connector, view)

        return view

        # return self

    @staticmethod
    def strings_to_buttons(
        strings: list[str], buttons_style: ButtonStyle = ButtonStyle.primary
    ) -> list[Button]:
        """Convert the strings to buttons."""
        return [
            Button(string, style=buttons_style or ButtonStyle.primary)
            for string in strings
        ]

    # TODO: [07.09.2023 by Mykola] Make it not `async`
    @abstractmethod
    async def get_static_buttons(self, flow_connector: FlowConnector) -> list[Button | str]:
        """Get the static buttons for the view."""
        raise NotImplementedError

    def _add_buttons(self, *buttons: Button | str):
        """Add buttons to the view."""
        for button in buttons:
            if isinstance(button, str):
                button = Button(button, style=self.buttons_style or ButtonStyle.primary)

            self.add_item(button)

    def _remove_button(self, button: Button):
        """Remove the button from the view."""
        self.children.remove(button)

    def _get_button_by_custom_id(self, custom_id: str) -> Button | None:
        """Get the button by its custom id."""
        logger.debug("Getting the button by its custom id from the view.")
        for item in self.children:
            if isinstance(item, Button) and item.custom_id == custom_id:
                return item
        else:
            logger.debug(f"Cannot find the button with custom id {custom_id} in {self.children=}")

        logger.debug(f"Trying to get the button from the parent view.")
        return (self._parent_view or self)._custom_id_to_button.get(custom_id)

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
    async def _defer(interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass
        except discord.NotFound:
            logger.warning(f"Interaction {interaction.id} was not found. Cannot defer the response.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(3),
        reraise=False,
        retry_error_callback=lambda _: None,
    )
    async def _update_view(self, interaction: discord.Interaction):
        """Update the view."""
        try:
            await interaction.response.edit_message(view=self)
        except discord.NotFound as exception:
            logger.warning(f"Interaction {interaction.id} was not found. Cannot update the view.")
            raise exception

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=False)
    async def _remove_view(interaction: discord.Interaction):
        try:
            await interaction.response.edit_message(view=None)
        except discord.NotFound as exception:
            logger.warning(f"Interaction {interaction.id} was not found. Cannot remove the view.")
            raise exception

    @abstractmethod
    async def process_button_click(self, button: Button, flow_connector: FlowConnector):
        """Process the button click."""
        raise NotImplementedError

    async def process_interaction(self, flow_connector: FlowConnector):
        """Process the interaction. Might be overridden in subclasses."""
        if not (button_custom_id := flow_connector.interaction.data.get("custom_id")):
            logger.error(f"Cannot find the custom id in {flow_connector.interaction.data=}")
            return

        if not (button := self._get_button_by_custom_id(button_custom_id)):
            logger.error(f"Cannot find the button with custom id {button_custom_id} in {self.children=}")
            return

        return await self.process_button_click(button, flow_connector)


class ConfirmButtonView(BaseView):
    """The view that has only one confirm button."""

    confirm_button_label: str

    _confirm_button: Button | None = None

    def __init__(self, confirm_button_label: str, **kwargs):
        """Initialize the view."""
        super().__init__(**kwargs)

        self.confirm_button_label = confirm_button_label

    @property
    def confirm_button(self) -> Button:
        if not self._confirm_button:
            self._confirm_button = Button(
                self.confirm_button_label, style=self.buttons_style or ButtonStyle.secondary
            )

        return self._confirm_button

    @confirm_button.setter
    def confirm_button(self, value: Button):
        self._confirm_button = value

    async def get_static_buttons(self, flow_connector: FlowConnector) -> list[Button | str]:
        return [self.confirm_button]

    async def on_submit(self, flow_connector: FlowConnector):
        """The method that is called when the confirm button is clicked."""
        await self._remove_view(flow_connector.interaction)

        raise ViewStepFinished()

    async def process_button_click(self, button: Button, flow_connector: FlowConnector):
        """Process the button click."""
        return await self.on_submit(flow_connector)


class StorageMixin(ABC):
    answers_storage: StorageBucketElement | None = None

    async def _get_user_answer(self) -> typing.Any:
        """Get the user answer."""
        if self.answers_storage:
            async with self.answers_storage as answers_storage:
                return answers_storage.get()

    async def _set_user_answer(self, user_answer: typing.Any):
        """Set the user answer."""
        if self.answers_storage:
            async with self.answers_storage as answers_storage:
                answers_storage.set(user_answer)

    async def clear_storage(self) -> None:
        """Clear the storage."""
        if self.answers_storage:
            await self.answers_storage.delete_data()


class ChooseOneOptionView(BaseView, StorageMixin):
    """The view that allows the user to choose only one option."""

    options: list[str] | typing.Callable[[], typing.Awaitable[list[str]]]

    def __init__(
        self,
        options: list[str | Button] | typing.Callable[[], typing.Awaitable[list[str]]],
        answers_storage: StorageBucketElement | None = None,
        **kwargs,
    ):
        """Initialize the view."""
        super().__init__(**kwargs)

        self.options = options

        # TODO: [07.09.2023 by Mykola] Use the unique `._step_name` for the storage key
        # self.answers_storage = answers_storage or StorageBucketElement(
        #     f"{self.__class__.__name__}::answers"
        # )
        self.answers_storage = answers_storage

    async def get_static_buttons(self, flow_connector: FlowConnector) -> list[str]:
        """Get the buttons for the view."""
        return self.options if isinstance(self.options, list) else await self.options()

    async def process_button_click(self, button: Button, flow_connector: FlowConnector):
        """Process the button click."""
        await self._remove_view(flow_connector.interaction)

        await self._set_user_answer(button.label)

        raise ViewStepFinished()


class MultipleAnswersView(ConfirmButtonView, StorageMixin):
    """The view that allows the user to choose multiple answers."""

    answers: (
        list[str] | BaseSubstitution | typing.Awaitable[list[str]] | typing.Callable[[], typing.Awaitable[list[str]]]
    )
    n_answers_to_select: int | None
    min_answers_allowed: int | None

    confirm_button_label: str | None = None

    _confirm_button: Button | None = None

    def __init__(
        self,
        answers: (
            list[str]
            | BaseSubstitution
            | typing.Awaitable[list[str]]
            | typing.Callable[[], typing.Awaitable[list[str]]]
        ),
        confirm_button_label: str,
        n_answers_to_select: int | None = None,
        min_answers_allowed: int | None = None,
        answers_storage: StorageBucketElement | None = None,
        answers_selection_style: ButtonStyle = ButtonStyle.success,
        confirm_button_style: ButtonStyle = ButtonStyle.primary,
        **kwargs,
    ):
        """Initialize the view."""
        super().__init__(confirm_button_label, **kwargs)

        self.answers = answers
        self.n_answers_to_select: int | None = n_answers_to_select
        self.min_answers_allowed: int | None = min_answers_allowed or n_answers_to_select

        self.answers_storage = answers_storage

        self.answers_selection_style = answers_selection_style
        self.confirm_button_style = confirm_button_style

    async def get_static_buttons(self, flow_connector: FlowConnector) -> list[Button | str]:
        """Get the buttons for the answers, and the confirm button."""
        confirm_button = copy(self.confirm_button)

        # Change the style of the confirm button
        confirm_button.style = self.confirm_button_style

        # Disable the confirm button by default, only if the `n_answers_to_select` or the `min_answers_allowed` is set
        confirm_button.disabled = bool(self.n_answers_to_select) or bool(self.min_answers_allowed)

        return [
            *(
                self.answers
                if isinstance(self.answers, list)
                else (
                    (
                        await self.answers.resolve(flow_connector)
                        if isinstance(self.answers, BaseSubstitution)
                        else (await self.answers if inspect.isawaitable(self.answers) else await self.answers())
                    )
                )
            ),
            confirm_button,
        ]

    def _update_user_answers(self, user_answers: list[str], button: Button) -> None:
        """Update the user answers."""
        if button.label in user_answers:
            user_answers.remove(button.label)
            button.style = self.buttons_style
        else:
            user_answers.append(button.label)
            button.style = self.answers_selection_style

    def _disable_unselected_buttons(self, user_answers: list[str]) -> None:
        """Disable the unselected buttons."""
        for item in self.children:
            # Skip the confirm button
            # TODO: [18.09.2023 by Mykola] This doesn't work here since all the buttons _must_ be
            #  copied for all the individual views
            # if item == self._confirm_button:
            #     continue
            if isinstance(item, Button) and item.label not in user_answers:
                item.disabled = True

    def _enable_all_buttons(self) -> None:
        """Enable all the buttons."""
        for item in self.children:
            # Skip the confirm button
            if item == self._confirm_button:
                continue
            if isinstance(item, Button):
                item.disabled = False

    def _change_confirm_button_state(self, enabled: bool = True) -> None:
        """Change the confirm button state."""
        for item in self.children:
            if isinstance(item, Button) and item.label == self.confirm_button_label:
                item.disabled = not enabled

    async def get_or_create_for_connector(
        self,
        flow_connector: FlowConnector,
        dynamic_buttons: list[str | Button] | None = None,
        force_init: bool = False,
        force_get: bool = False,
        from_step_run: bool = False,
    ) -> typing.Self:
        if from_step_run:
            # Clear the storage
            await self.clear_storage()

        return await super().get_or_create_for_connector(
            flow_connector, dynamic_buttons, force_init, force_get, from_step_run
        )

    async def process_button_click(self, button: Button, flow_connector: FlowConnector):
        """Save the answer and check whether the `n_answers_to_select` is reached."""

        if button.label == self.confirm_button.label:
            # Remove the view from the message
            return await self.on_submit(flow_connector)

        # Save the answer
        user_answers: list[str] | None = await self._get_user_answer() or []
        self._update_user_answers(user_answers, button)
        await self._set_user_answer(user_answers)

        if self._confirm_button:
            if self.n_answers_to_select:
                if len(user_answers) >= self.n_answers_to_select:
                    self._disable_unselected_buttons(user_answers)
                else:
                    self._enable_all_buttons()

            if self.min_answers_allowed:
                if len(user_answers) >= self.min_answers_allowed:
                    self._change_confirm_button_state(enabled=True)
                else:
                    self._change_confirm_button_state(enabled=False)

            return await self._update_view(flow_connector.interaction)

        else:
            return await self._defer(flow_connector.interaction)


# region ActionButtonsView
DEFAULT_ACTION_BUTTONS_VIEW_CONFIRM_BUTTON_LABEL = "Confirm"


class ActionButtonsView(ConfirmButtonView):
    """The view that has action buttons."""

    action_buttons: list[ActionButton]

    one_time_view: bool = False
    force_stay_on_step: bool = False
    force_confirm_button: bool = False

    def __init__(
        self,
        action_buttons: list[ActionButton],
        force_stay_on_step: bool = False,
        force_confirm_button: bool = False,
        **kwargs,
    ):
        """Initialize the view."""
        self.action_buttons = action_buttons

        self.one_time_view = kwargs.pop("one_time_view", False)
        self.force_stay_on_step = force_stay_on_step
        self.force_confirm_button = force_confirm_button

        super().__init__(
            confirm_button_label=kwargs.pop("confirm_button_label", DEFAULT_ACTION_BUTTONS_VIEW_CONFIRM_BUTTON_LABEL),
            **kwargs,
        )

    async def get_static_buttons(self, flow_connector: FlowConnector) -> list[Button]:
        """Get the buttons for the view."""
        return self.action_buttons + (
            await super().get_static_buttons(flow_connector)
            if not self.one_time_view or self.force_confirm_button
            else []
        )

    async def process_button_click(self, button: Button, flow_connector: FlowConnector):
        """Process the button click."""
        from .buttons import ActionButton

        if button.label == self.confirm_button.label:
            # Remove the view from the message
            return await self.on_submit(flow_connector)

        raise_view_step_finished: bool = False

        try:
            if self.one_time_view:
                await self.on_submit(flow_connector)
            else:
                await self._defer(flow_connector.interaction)
        except ViewStepFinished:
            raise_view_step_finished = True
            pass

        if not isinstance(button, ActionButton):
            raise ValueError("The button must be an instance of `ActionButton`.")

        await button.trigger_action(flow_connector)

        if raise_view_step_finished and not self.force_stay_on_step:
            raise ViewStepFinished()


# endregion
