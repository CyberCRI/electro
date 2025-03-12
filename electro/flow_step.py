"""The `BaseFlowStep` class."""

from __future__ import annotations

import json
import pathlib
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import discord
from openai import NOT_GIVEN

from .contrib.storage_buckets import BaseStorageBucketElement, StorageBucketElement
from .contrib.views import BaseView, ViewStepFinished
from .flow_connector import FlowConnectorEvents

# from decorators import with_constant_typing
from .settings import settings
from .substitutions import BaseSubstitution, GlobalAbstractChannel, resolve_channel
from .toolkit.loguru_logging import logger
from .toolkit.openai_client import async_openai_client
from .toolkit.templated_i18n import TemplatedString
from .types_ import Channel, MessageToSend

if typing.TYPE_CHECKING:
    from .flow import FlowConnector


class FlowStepDone(Exception):
    """The exception that is raised when the `BaseFlowStep` is finished."""

    pass


class BaseFlowStep(ABC):
    """The base class for `BaseFlowStep`."""

    _step_name: str  # Defined by the metaclass `FlowMeta`

    non_blocking: bool = False
    _testing: bool = False

    @abstractmethod
    async def run(self, connector: FlowConnector) -> list[MessageToSend] | None:
        """Run the `BaseFlowStep`. Called when the `BaseFlowStep` is started."""
        raise NotImplementedError

    @abstractmethod
    async def process_response(self, connector: FlowConnector):
        """Process the response."""
        raise NotImplementedError


class MessageFormatterMixin:
    """The mixin for formatting messages."""

    substitutions: dict[str, str] | None = None

    async def _get_formatted_message(self, message: TemplatedString, connector: FlowConnector, **kwargs) -> str:
        """Get the formatted message."""
        generic_substitutions: dict[str, str | int | BaseSubstitution] = (
            connector.user_data | (connector.substitutions or {}) | (self.substitutions or {}) | kwargs
        )

        variables_used_in_message = message.get_identifiers()
        logger.debug(
            f"Variables used in the message: {variables_used_in_message}, {generic_substitutions=}, {message=}"
        )

        substitutions: dict[str, str | int] = {
            key: (
                await value.resolve(connector)
                if isinstance(value, BaseSubstitution)
                else await value.get_data() if isinstance(value, BaseStorageBucketElement) else value
            )
            for key, value in generic_substitutions.items()
            if key in variables_used_in_message
        }

        return message.safe_substitute(
            **substitutions,
        )


@dataclass(kw_only=True)
class FilesMixin:
    file: discord.File | typing.BinaryIO | pathlib.Path | BaseSubstitution | None = None
    files: list[discord.File | typing.BinaryIO | pathlib.Path | BaseSubstitution] | None = None

    async def _get_files_to_send(self, connector: FlowConnector) -> list[discord.File]:
        """Get the files to send."""
        if self.file and self.files:
            # TODO: [18.11.2023 by Mykola] Use `overload` to type-hint prohibit both `file` and `files` at the same time
            raise ValueError("You can't specify both `file` and `files`.")

        # Resolve the files if they are `BaseSubstitution`s
        files: list[discord.File | typing.BinaryIO | pathlib.Path | None] = [
            await file.resolve(connector) if file and isinstance(file, BaseSubstitution) else file
            for file in (self.files or ([self.file] if self.file else []))
        ]

        # Convert the files to `discord.File`s if they are not
        files = [file if isinstance(file, discord.File) else (discord.File(file) if file else None) for file in files]

        # Remove the `None`s
        files = [file for file in files if file]

        return files


class CallbackHandlerStep(BaseFlowStep):
    """The Step that calls the callback."""

    _step: BaseFlowStep | None = None

    def __init__(
        self,
        callback: typing.Callable[[FlowConnector], typing.Awaitable[None]],
        *,
        process_response_callback: typing.Callable[[FlowConnector], typing.Awaitable[None]] = None,
        non_blocking: bool = False,
        dont_raise_flow_step_done: bool = False,
        skip_on_failure: bool = False,
    ):
        self.callback = callback
        self.process_response_callback = process_response_callback
        self.non_blocking = non_blocking
        self.dont_raise_flow_step_done = dont_raise_flow_step_done
        self.skip_on_failure = skip_on_failure

        self._step = None

    # TODO: [2024-07-19 by Mykola] Use the decorators
    # @with_constant_typing()
    async def run(self, connector: FlowConnector):
        try:
            result = await self.callback(connector)

            if isinstance(result, BaseFlowStep):
                # If the callback returns a `BaseFlowStep`, save it
                # (for the `process_response` method)
                self._step = result

                # Run the `BaseFlowStep`
                await result.run(connector)
        except Exception as e:
            if self.skip_on_failure:
                logger.exception(e)

                raise FlowStepDone() from e
            else:
                raise e

        if self.non_blocking:
            raise FlowStepDone()

    async def process_response(self, connector: FlowConnector):
        if self.process_response_callback:
            await self.process_response_callback(connector)

        elif self._step:
            await self._step.process_response(connector)

        elif not self.dont_raise_flow_step_done:
            raise FlowStepDone()

    async def on_response(self, callback: typing.Callable[[FlowConnector], typing.Awaitable[None]]):
        """Register an `process_response` callback."""
        self.process_response_callback = callback


def callback_handler(
    *,
    process_response_callback: typing.Callable[[FlowConnector], typing.Awaitable[None]] = None,
    non_blocking: bool = False,
    dont_raise_flow_step_done: bool = False,
    skip_on_failure: bool = False,
):
    """A decorator for creating a `CallbackHandlerStep`."""

    def decorator(callback: typing.Callable[[FlowConnector], typing.Awaitable[None]]):
        return CallbackHandlerStep(
            callback,
            process_response_callback=process_response_callback,
            non_blocking=non_blocking,
            dont_raise_flow_step_done=dont_raise_flow_step_done,
            skip_on_failure=skip_on_failure,
        )

    return decorator


@dataclass
class MessageFlowStep(BaseFlowStep, FilesMixin, MessageFormatterMixin):
    """The class for `MessageFlowStep`."""

    message: TemplatedString | None = None
    response_message: TemplatedString | None = None

    channel_to_send_to: discord.abc.Messageable | BaseSubstitution | GlobalAbstractChannel | None = None

    substitutions: dict[str, str] | None = None

    view: BaseView | None = None

    validator: typing.Callable[[str], bool] | None = None
    validator_error_message: TemplatedString | None = None

    # TODO: [27.09.2023 by Mykola] Make this automatic, on the `Flow` level
    save_response_to_storage: StorageBucketElement | None = None

    non_blocking: bool = False
    _testing: bool = False

    @staticmethod
    async def _resolve_channel_to_send_to(
        channel_to_send_to: Channel | BaseSubstitution[Channel] | GlobalAbstractChannel | None,
        connector: FlowConnector,
    ) -> Channel:
        if not channel_to_send_to:
            return connector.channel

        if isinstance(channel_to_send_to, BaseSubstitution):
            return await channel_to_send_to.resolve(connector)

        if isinstance(channel_to_send_to, GlobalAbstractChannel):
            return await resolve_channel(channel_to_send_to, connector.user)

        return channel_to_send_to

    async def send_message(
        self,
        connector: FlowConnector,
        message: TemplatedString | str,
        channel: discord.abc.Messageable | BaseSubstitution[discord.abc.Messageable] | None = None,
        view: BaseView | None = None,
    ) -> MessageToSend:
        """Send the message."""
        message: str | None = (
            await self._get_formatted_message(message, connector) if isinstance(message, TemplatedString) else message
        )

        # files = await self._get_files_to_send(connector)

        channel_to_send_to: Channel = await self._resolve_channel_to_send_to(
            channel or self.channel_to_send_to, connector
        )

        # view_to_sent = await view.get_or_create_for_connector(connector, from_step_run=True) if view else None
        await connector.interface.send_json(
            {
                "message": message,
                "to": channel_to_send_to.id,
            }
        )

    # TODO: [2024-07-19 by Mykola] Use the decorators
    # @with_constant_typing()
    async def run(
        self,
        connector: FlowConnector,
        channel_to_send_to: Channel | BaseSubstitution | None = None,
    ) -> MessageToSend | None:
        """Run the `BaseFlowStep`."""

        message: MessageToSend = await self.send_message(
            connector, self.message, channel=channel_to_send_to or connector.channel, view=self.view
        )

        if self.non_blocking:
            await self.respond(connector)

            raise FlowStepDone()

        # TODO: [2025-03-03 by Mykola] Allow sending multiple messages
        return message

    async def respond(self, connector: FlowConnector) -> discord.Message:
        """Respond to the user."""
        if self.response_message:
            return await self.send_message(connector, self.response_message, channel=connector.channel)

    async def process_response(self, connector: FlowConnector):
        """Process the response. If the `.response_message` is set, send it."""
        if self.view and connector.event == FlowConnectorEvents.BUTTON_CLICK and connector.interaction:
            try:
                view_for_connector = await self.view.get_or_create_for_connector(connector)
                return await view_for_connector.process_interaction(connector)
            except ViewStepFinished:
                pass

        # TODO: [23.11.2023 by Mykola] Use Whisper to transcribe the audio message into text

        if self.validator:
            if not self.validator(connector.message.content):
                error_message = (
                    await self._get_formatted_message(self.validator_error_message, connector)
                    if self.validator_error_message
                    else "Invalid input."
                )

                await connector.channel.send(error_message)
                return

        if self.save_response_to_storage:
            await self.save_response_to_storage.set_data(connector.message.content)

        await self.respond(connector)

        raise FlowStepDone()


class DirectMessageFlowStep(MessageFlowStep):
    """The same as `MessageFlowStep`, but sends the message to the user's DMs."""

    async def run(self, connector: FlowConnector, channel_to_send_to: discord.abc.Messageable | None = None):
        if not channel_to_send_to and not isinstance(connector.channel, discord.DMChannel):
            channel_to_send_to = GlobalAbstractChannel.DM_CHANNEL

        return await super().run(connector, channel_to_send_to=channel_to_send_to)


@dataclass(kw_only=True)
class SendImageFlowStep(MessageFlowStep):
    """The Step that sends an image."""

    language: str | None = None

    force_blocking_step: bool = False

    def __post_init__(self):
        """Post-initialization."""
        # If the user doesn't want to force the blocking step, set the `non_blocking` flag to `True`
        if not self.force_blocking_step:
            self.non_blocking = True

        # If the language is set, try to use the language-specific file
        if self.language:
            language = self.language.lower()
            language_specific_file = self.file.with_stem(f"{self.file.stem}__{language}")

            if language_specific_file.exists():
                self.file = language_specific_file
            else:
                logger.warning(
                    f"In step {self.__class__.__name__}: "
                    f"Language-specific file {language_specific_file} does not exist. Using the default."
                )


# TODO: [26.09.2023 by Mykola] Move to a separate file
class ChatGPTResponseFormat(str, Enum):
    """The format of the response from the ChatGPT API."""

    AUTO = "auto"
    TEXT = "text"
    JSON_OBJECT = "json_object"


class ChatGPTMixin:
    """The mixin that allows for getting responses from the ChatGPT API."""

    @staticmethod
    async def get_response_from_chat_gpt(
        prompt: str,
        system_message: str | None = None,
        response_format: ChatGPTResponseFormat = ChatGPTResponseFormat.AUTO,
    ) -> str:
        """Get the response from the ChatGPT API."""
        logger.debug(f"Getting ChatGPT response for prompt {prompt=} and {system_message=} in {response_format=}...")

        completion_messages = []

        if system_message:
            completion_messages.append(
                {
                    "role": "system",
                    "content": system_message.strip(),
                },
            )

        completion_messages.append(
            {
                "role": "user",
                "content": prompt.strip(),
            },
        )

        response_format: str | dict[str, str] = (
            NOT_GIVEN
            if response_format == ChatGPTResponseFormat.AUTO
            else (
                {
                    "type": (
                        response_format.value if isinstance(response_format, ChatGPTResponseFormat) else response_format
                    )
                }
            )
        )

        completion = await async_openai_client.chat.completions.create(
            model=settings.OPENAI_CHAT_COMPLETION_MODEL, messages=completion_messages, response_format=response_format
        )

        message = completion.choices[0].message
        logger.debug(f"Got ChatGPT response: {message=}")

        return message.content


@dataclass
class ChatGPTRequestMessageFlowStep(MessageFlowStep, ChatGPTMixin):
    """The Step that gets the response from the ChatGPT API for sending a message."""

    message_prompt: TemplatedString | None = None
    response_message_prompt: TemplatedString | None = None

    response_format: ChatGPTResponseFormat | str = ChatGPTResponseFormat.AUTO

    save_prompt_response_to_storage: StorageBucketElement | None = None
    parse_json_before_saving: bool | None = None

    async def _get_formatted_message(self, message: TemplatedString, connector: FlowConnector, **kwargs) -> str:
        """Get the formatted message."""
        if not self.message_prompt:
            return await super()._get_formatted_message(message, connector, **kwargs)

        # Send the typing indicator
        await connector.channel.trigger_typing()

        prompt_response = await self.get_response_from_chat_gpt(
            await super()._get_formatted_message(self.message_prompt, connector, **kwargs),
            response_format=self.response_format,
        )

        if self.save_prompt_response_to_storage:
            response_to_save = prompt_response

            # Try to parse the JSON response before saving
            if self.parse_json_before_saving or (  # Parse JSON if the flag is set
                # Or if the response format is JSON and the flag is not set (default) and `!= False` (explicitly set)
                self.parse_json_before_saving is None
                and self.response_format == ChatGPTResponseFormat.JSON_OBJECT
            ):
                try:
                    response_to_save: Any = json.loads(prompt_response)
                    logger.debug(f"Parsed the `{self.__class__.__name__}` JSON response: {response_to_save=}")
                except json.JSONDecodeError:
                    logger.exception(
                        f"Failed to parse `{self.__class__.__name__}` the JSON response: {prompt_response=}. "
                        f"Saving as a string."
                    )

            await self.save_prompt_response_to_storage.set_data(response_to_save)

        return await super()._get_formatted_message(message, connector, prompt_response=prompt_response, **kwargs)
