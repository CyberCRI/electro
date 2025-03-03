"""The `Flow` class."""

from __future__ import annotations

import typing
from abc import ABC, ABCMeta, abstractmethod

from stringcase import snakecase

from . import types_ as types
from .contrib.storage_buckets import BaseStorageBucket, BaseStorageBucketElement
from .flow_connector import FlowConnector, FlowConnectorEvents
from .flow_step import BaseFlowStep, FlowStepDone
from .scopes import FlowScopes

# from decorators import forbid_concurrent_execution, with_constant_typing
from .settings import settings
from .substitutions import BaseSubstitution
from .toolkit.loguru_logging import logger
from .triggers import BaseFlowTrigger

STATE_SEPARATOR = ":"


class FlowFinished(Exception):
    """The exception that is raised when the `Flow` is finished."""

    pass


class FlowMeta(ABCMeta):
    def __new__(mcs: typing.Type[FlowMeta], name, bases, namespace, **kwargs):
        cls: FlowMeta = super(FlowMeta, mcs).__new__(mcs, name, bases, namespace, **kwargs)

        try:
            steps: dict[str, BaseFlowStep | BaseFlow] = {}

            # Get all the steps from the bases
            for base in reversed(bases):  # Reversed so that the first base gets the priority (as in MRO?)
                if hasattr(base, "_steps"):
                    # noinspection PyProtectedMember
                    steps.update(base._steps)

            for name_, prop in namespace.items():
                if isinstance(prop, (BaseFlowStep, BaseFlow)):
                    if (
                        hasattr(prop, "_step_name")
                        and getattr(prop, "_step_name", None)  # Sometimes it's just `None`. No clue why ¯\_(ツ)_/¯
                        and getattr(prop, "_step_name", None) != name_
                    ):
                        logger.warning(f"Step {name_} already has a _step_name attribute. Overwriting it.")

                    # Set the step name for the step, used (mostly) for logging and user-input validation errors
                    prop._step_name = name_

                    steps[name_] = prop

            cls._steps = steps

            cls._state_prefix = snakecase(name)
        except NameError:
            # This only happens when it's the `BaseFlow` class that is being initialized. In this case, `BaseFlow`
            #  is not defined yet, so we just skip setting the steps for it since we don't need them in it `BaseFlow`.
            pass

        return cls


class BaseFlow(ABC, metaclass=FlowMeta):
    """The base class for `Flow`."""

    _scope: FlowScopes = FlowScopes.USER

    _step_name: str | None = None  # Defined by the metaclass `FlowMeta`, but only if the Flow is a sub-Flow

    _triggers: list[BaseFlowTrigger] = []
    _substitutions: dict[str, str] | None = None

    # Reset specific storages when the flow is run
    _storages_to_reset_on_flow_run: list[BaseStorageBucket | BaseStorageBucketElement] | None = None

    # Is set when the subclass of `Flow` (or `BaseFlow`) is initialized
    _state_prefix: str

    # Steps are set when the subclass of `Flow` (or `BaseFlow`) is initialized
    _steps: dict[str, BaseFlowStep | BaseFlow]

    iterables: typing.List | BaseSubstitution[typing.Iterable] = []
    # _iterables: typing.List | None = None

    iterable_substitution_name = "iterable"

    def _get_connector_state(self, connector: FlowConnector) -> str:
        """Get the state for the connector, based on the scope."""
        match self._scope:
            case FlowScopes.USER:
                return connector.user_state
            case FlowScopes.CHANNEL:
                return connector.channel_state
            # case FlowScopes.GUILD:
            #     return connector.guild_state
            case _:
                raise ValueError(f"Unknown scope: {self._scope}. Supported scopes: {FlowScopes.__members__}")

    def _set_connector_state(self, connector: FlowConnector, state: str):
        """Set the state for the connector, based on the scope."""
        match self._scope:
            case FlowScopes.USER:
                connector.user_state = state
            case FlowScopes.CHANNEL:
                connector.channel_state = state
            # case FlowScopes.GUILD:
            #     connector.guild_state = state
            case _:
                raise ValueError(f"Unknown scope: {self._scope}. Supported scopes: {FlowScopes.__members__}")

    @abstractmethod
    async def check(self, connector: FlowConnector) -> bool:
        """Check if the `Flow` can be run."""
        raise NotImplementedError

    async def resolve_iterables(self, connector: FlowConnector) -> typing.List:
        """Resolve the iterables for the `Flow`."""
        iterables = self.iterables

        if isinstance(iterables, BaseSubstitution):
            iterables = await iterables.resolve(connector)

        if not isinstance(iterables, list):
            iterables = list(iterables)

        return iterables

    async def get_iterables(self, connector: FlowConnector) -> typing.List:
        """Get the iterables for the `Flow`."""
        # if not self._iterables and self.iterables:
        #     self._iterables = await self.resolve_iterables(connector)
        #
        # return self._iterables

        # The design above doesn't work for multiple users, so we need to resolve the iterables
        #  every time
        return await self.resolve_iterables(connector)

    @abstractmethod
    async def step(
        self, connector: FlowConnector, initial: bool = False, upper_level_state: str | None = None
    ) -> list[types.MessageToSend] | None:
        """Process the response in the current step of the `Flow`."""
        raise NotImplementedError

    @abstractmethod
    async def run(
        self, connector: FlowConnector, upper_level_state: str | None = None
    ) -> list[types.MessageToSend] | None:
        """Start the `Flow`."""
        raise NotImplementedError


class Flow(BaseFlow):
    """
    The class for `Flow`.

    `Flow` is a collection of `BaseFlowStep`s, each representing a particular input from the user.

    When a `BaseFlowStep` is run, it sets a state for the user. The next time the `Flow` is run,
    is checks the state of the user and runs the next `BaseFlowStep` if the state matches.
    """

    _acceptable_continue_events: list[FlowConnectorEvents] = [
        FlowConnectorEvents.MESSAGE,
        FlowConnectorEvents.BUTTON_CLICK,
    ]

    def __init__(
        self,
        triggers: typing.Optional[list[BaseFlowTrigger]] = None,
        substitutions: typing.Optional[dict[str, str]] = None,
        iterables: typing.Optional[typing.Iterable | BaseSubstitution[typing.Iterable]] = None,
        iterable_substitution_name: str | None = None,
    ):
        self._triggers = [*self._triggers, *(triggers or [])]
        self._substitutions = (self._substitutions or {}) | (substitutions or {})

        self.iterables = iterables or self.iterables
        self.iterable_substitution_name = iterable_substitution_name or self.iterable_substitution_name

    def _check_scope(self, scope: FlowScopes | None) -> bool:
        """If `scope` is provided, check if the scope matches the scope of the `Flow`."""
        if scope and self._scope != scope:
            return False

        return True

    async def check(self, connector: FlowConnector, scope: FlowScopes | None = None) -> bool:
        """Check if the `Flow` can be run."""
        if ((connector_event := connector.event) and connector_event not in self._acceptable_continue_events) or (
            connector_event == FlowConnectorEvents.MESSAGE and not self._check_scope(scope)
        ):
            return False

        # Get the state to check based on the scope
        state_to_check = self._get_connector_state(connector)

        if (
            self._state_prefix
            and state_to_check
            and state_to_check.startswith(f"{self._state_prefix}{STATE_SEPARATOR}")
        ):
            return True

        return False

    async def check_triggers(self, connector: FlowConnector, scope: FlowScopes | None = None) -> bool:
        """Check if the `Flow` can be triggered."""
        return any([await trigger.check(connector, scope=scope) for trigger in self._triggers])

    async def _update_connector_pre_run(self, connector: FlowConnector, *_, **__kwargs) -> FlowConnector | None:
        """Update the connector before running the `Flow`."""
        return connector

    async def run(
        self, connector: FlowConnector, upper_level_state: str | None = None
    ) -> list[types.MessageToSend] | None:
        """Start the `Flow`."""
        # Make sure there are steps in the `Flow`
        if not self._steps:
            raise ValueError("There are no steps in the flow.")

        # Reset the storages that need to be reset
        for storage in self._storages_to_reset_on_flow_run or []:
            if issubclass(storage, BaseStorageBucket):
                await storage.empty()
            elif isinstance(storage, BaseStorageBucketElement):
                await storage.delete_data()
            else:
                raise TypeError(f"Unknown storage type: {type(storage)}")

        connector = await self._update_connector_pre_run(connector, **(connector.extra_data or {})) or connector

        return await self.step(connector, initial=True, upper_level_state=upper_level_state)

    # TODO: [2024-07-19 by Mykola] Use the decorators
    # @forbid_concurrent_execution()
    # @with_constant_typing(run_only_on_events=[FlowConnectorEvents.MESSAGE])
    async def step(
        self, connector: FlowConnector, initial: bool = False, upper_level_state: str | None = None
    ) -> list[types.MessageToSend] | None:
        """
        Process the response in the current step of the `Flow`.

        If the `FlowStepDone` exception is raised, run the next step.
        """

        # Check substitutions
        if self._substitutions:
            connector.substitutions = self._substitutions | (connector.substitutions or {})

        while True:
            if initial:
                # Set `is_go_back_command` and `is_reload_command` to `False` so that they're defined
                is_go_back_command = False
                is_reload_command = False

                # Set the iterator index to 0
                iterator_index = 0  # TODO: [09.11.2023 by Mykola]

                # Always treat the step to run as the next step
                next_step_index = 0
            else:
                current_state = self._get_connector_state(connector)
                iterator_index, current_flow_step_name = (
                    current_state.removeprefix(
                        STATE_SEPARATOR.join(
                            [
                                upper_level_state if upper_level_state is not None else "",
                                self._state_prefix,
                            ]
                        ).strip(STATE_SEPARATOR)
                    )
                    .removeprefix(STATE_SEPARATOR)
                    .split(STATE_SEPARATOR)[0:2]
                )
                logger.info(f"Current flow step name: {current_flow_step_name} [{connector.user.id=}]")

                iterator_index: int = int(iterator_index)

                # Process the response
                is_go_back_command = connector.message and connector.message.content == settings.GO_BACK_COMMAND
                is_reload_command = connector.message and connector.message.content == settings.RELOAD_COMMAND
                try:
                    if is_go_back_command or is_reload_command:
                        # Change the message content, so we don't process the "go back" command again
                        connector.message.content = ""

                        raise FlowStepDone()

                    current_flow_step: BaseFlowStep | BaseFlow = self._steps[current_flow_step_name]

                    if isinstance(current_flow_step, BaseFlow):
                        upper_level_state_parts = (
                            upper_level_state.split(STATE_SEPARATOR) if upper_level_state is not None else []
                        )
                        return await current_flow_step.step(
                            connector,
                            upper_level_state=STATE_SEPARATOR.join(
                                map(
                                    str,
                                    [
                                        *upper_level_state_parts,
                                        self._state_prefix,
                                        iterator_index,
                                        current_flow_step_name,
                                    ],
                                )
                            ),
                        )

                    return await current_flow_step.process_response(connector)
                # If the response has raised the `FlowStepDone` exception, get the next step
                except (FlowStepDone, FlowFinished):
                    next_step_index = list(self._steps.keys()).index(current_flow_step_name) + 1

                    logger.info(
                        f"Current flow step done. Next step index: {next_step_index} " f"[{connector.user.id=}]"
                    )

            # Try to get the next step. On `IndexError`, meaning that there are no more steps in
            #  this flow, raise the `FlowFinished` exception.
            try:
                if is_go_back_command or is_reload_command:
                    # Get the index of the last non-blocking step
                    next_step_index = next(
                        index
                        for index, step in reversed(
                            list(enumerate(self._steps.values()))[: next_step_index - (1 if is_go_back_command else 0)]
                        )
                        if isinstance(step, BaseFlowStep) and not step.non_blocking
                    )
                next_step_name, next_step = list(self._steps.items())[next_step_index]
                logger.info(f"Next step name: {next_step_name} [{connector.user.id=}]")
            except (IndexError, StopIteration):
                if (
                    (iterables := await self.get_iterables(connector))
                    # and isinstance(
                    #     iterables, list
                    # )  # TODO: [09.11.2023 by Mykola] Allow for other iterables
                    and iterator_index < (len(iterables) - 1)
                ):
                    iterator_index += 1
                    next_step_index = 0

                    next_step_name, next_step = list(self._steps.items())[next_step_index]
                    logger.info(f"Next step name: {next_step_name} [{connector.user.id=}]")
                else:
                    raise FlowFinished()

            # Set the state for the user
            default_state_parts: list[str] = [self._state_prefix, iterator_index, next_step_name]
            state_parts = [upper_level_state, *default_state_parts] if upper_level_state else default_state_parts

            self._set_connector_state(connector, STATE_SEPARATOR.join(map(str, state_parts)))

            if (iterables := await self.get_iterables(connector)) and isinstance(self.iterable_substitution_name, str):
                connector.substitutions[self.iterable_substitution_name] = iterables[iterator_index]

            # Run the next step
            try:
                logger.info(f"Running the next step: {next_step_name=} {next_step=} [{connector.user.id=}]")

                if isinstance(next_step, BaseFlow):
                    return await next_step.run(connector, upper_level_state=self._get_connector_state(connector))

                return await next_step.run(connector)
            # It is possible that the next step is also finished, so it has an opportunity
            #  to raise the `FlowStepDone` exception itself.
            except FlowStepDone:
                logger.info(f"Next step done. Next step index: {next_step_index} [{connector.user.id=}]")

                if initial:
                    next_step_index += 1
                    initial = False
