"""Chat helpers."""

import asyncio
import json
from contextvars import ContextVar
from typing import Any, AsyncGenerator, Callable, Tuple

from httpx import ReadTimeout
from openai.types.beta import Thread
from openai.types.beta.assistant_stream_event import (
    AssistantStreamEvent,
    ThreadMessageCreated,
    ThreadMessageDelta,
    ThreadRunCancelled,
    ThreadRunCancelling,
    ThreadRunCompleted,
    ThreadRunCreated,
    ThreadRunExpired,
    ThreadRunFailed,
    ThreadRunInProgress,
    ThreadRunQueued,
    ThreadRunRequiresAction,
    ThreadRunStepCancelled,
    ThreadRunStepFailed,
)
from openai.types.beta.threads import RequiredActionFunctionToolCall
from openai.types.beta.threads.message import Message
from openai.types.beta.threads.run_submit_tool_outputs_params import ToolOutput

from .schemas import AssistantMessageDeltaType
from .settings import settings
from .toolkit.loguru_logging import logger
from .toolkit.openai_client import async_openai_client


async def create_new_chat_thread() -> Thread:
    """
    Create an Assistant chat thread.

    Returns:
        str: The `.thread_id` of the created chat thread
    """

    return await async_openai_client.beta.threads.create()


async def get_assistant_response(
    assistant_id: str,
    prompt: str,
    thread_id: str,
    functions: dict[str, Callable],
    **kwargs: dict[str, Any],
) -> str:
    """
    Get the assistant response.

    Args:
        assistant_id (str): The ID of the assistant to use
        prompt (str): The prompt to send to the assistant
        thread_id (str): The ID of the chat thread
        functions (dict[str, callable]): The functions to execute
        **kwargs (dict[str, Any]): The keyword arguments to pass to the functions

    Returns:
        str: The response from the assistant
    """

    logger.info(f"Getting the Assistant response for {prompt=}...")

    # TODO: [2025-07-10 by Mykola] Allow different assistants to be chosen by the user and/or depending on the use-case
    assistant = await async_openai_client.beta.assistants.retrieve(assistant_id)

    thread = await async_openai_client.beta.threads.retrieve(thread_id)

    # TODO: [2025-07-11 by Mykola] Stop all the active runs for the thread before creating a new one

    thread_message = await async_openai_client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=prompt
    )
    logger.info(f"Created a message in Assistants API: {thread_message=}, {thread_id=}.")

    run = await async_openai_client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
        # max_prompt_tokens=settings.OPENAI_MAX_PROMPT_TOKENS,
        # max_completion_tokens=settings.OPENAI_MAX_COMPLETION_TOKENS,
    )
    logger.info(f"Run the thread with: {thread_message=}, {thread_id=}. Got {run=}")

    # Initial sleep, just to give the API some time to process the request
    await asyncio.sleep(3)

    re_run_count = 0
    run_retry_count = 0
    while True:
        for retry_n in range(1, settings.OPENAI_API_RUN_FETCH_RETRIES + 1):
            logger.info(f"Trying to retrieve a run. Try #{retry_n}: {run.id=}")
            try:
                run = await async_openai_client.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run.id, timeout=10
                )
                logger.info(f"Retrieved a run: {run=} for {thread_id=}")
                break
            except ReadTimeout as exception:
                logger.exception(
                    f"Hit a ReadTimeout while retrieving a run: {thread_id=}, {run.id=}", exc_info=exception
                )

                logger.info("Sleeping for 1 second")
                await asyncio.sleep(1)

        if run.status == "completed":
            break

        elif run.status == "requires_action":
            if not functions:
                raise ValueError(f"The functions are not set: {functions=}")

            tool_outputs: list[ToolOutput] = []
            # Get the action to perform
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                # Get the function to execute
                function_to_execute = functions.get(tool_call.function.name)

                if not function_to_execute:
                    raise ValueError(f"The function to execute is not found: {tool_call.function.name}")

                # Execute the function
                action_output = await function_to_execute(**(kwargs | json.loads(tool_call.function.arguments)))

                # Add the output to the tool outputs
                tool_outputs.append(
                    ToolOutput(
                        tool_call_id=tool_call.id,
                        output=action_output,
                    )
                )

            # Submit tool outputs
            await async_openai_client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )

        elif run.status == "in_progress":
            logger.debug(f"Run {run.id} is in progress. Sleeping for 1 second...")
            await asyncio.sleep(1)

        elif run.status == "queued":
            logger.debug(f"Run {run.id} is queued. Sleeping for 1 second...")
            await asyncio.sleep(1)

        elif run.status == "failed":
            logger.error(f"Run {run.id} failed: {run.last_error=}")

            if run.last_error and run.last_error.code == "rate_limit_exceeded":
                if re_run_count >= settings.OPENAI_API_RUN_FAILED_RETRIES:
                    raise ValueError(f"Reached the maximum number of RUN_FAILED retries: {re_run_count=} for {run.id=}")

                logger.warning(f"Rate limit exceeded for {run.id=}. Sleeping for 5 second...")
                await asyncio.sleep(5)

                continue

            if run_retry_count >= settings.OPENAI_API_RUN_RETRIED_RETRIES:
                raise ValueError(f"Reached the maximum number of RUN_RETRIED retries: {run_retry_count=} for {run.id=}")

            # Retry the run
            run = await async_openai_client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id,
            )
            logger.info(f"Re-run the thread with: {thread_message=}, {thread_id=}. Got {run=}")

            re_run_count += 1
            await asyncio.sleep(1)

        else:
            raise ValueError(f"The Run status is unexpected: {run.status}")

    thread_messages = await async_openai_client.beta.threads.messages.list(thread_id=thread.id)
    response_message_text: str = thread_messages.data[0].content[0].text.value

    return response_message_text


async def _process_assistant_tool_calls(
    tool_calls: list[RequiredActionFunctionToolCall],
    tools: dict[str, Callable],
    **kwargs: dict[str, Any],
) -> list[ToolOutput]:
    """
    Process the assistant tool calls.

    Args:
        tool_calls (list[ToolOutput]): The tool calls to process
        functions (dict[str, callable]): The functions to execute
        **kwargs (dict[str, Any]): The keyword arguments to pass to the functions

    Returns:
        list[ToolOutput]: The processed tool outputs
    """

    tool_outputs = []
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_to_execute = tools.get(function_name)

        if not function_to_execute:
            raise ValueError(f"The function to execute is not found: {function_name}")

        # Execute the function with combined kwargs
        function_args = json.loads(tool_call.function.arguments)
        action_output = await function_to_execute(**(kwargs | function_args))

        # Add the output to the tool outputs
        tool_outputs.append(
            ToolOutput(
                tool_call_id=tool_call.id,
                output=action_output,
            )
        )

    return tool_outputs


current_message_id: ContextVar[str | None] = ContextVar("current_message_id", default=None)


async def _process_assistant_event(
    event: AssistantStreamEvent,
    thread: Thread,
    tools: dict[str, Callable],
    **kwargs: dict[str, Any],
) -> AsyncGenerator[Tuple[str, AssistantMessageDeltaType], None]:
    """
    Process the assistant event.

    Args:
        event (AssistantStreamEvent): The event to process
        thread (Thread): The thread to process the event for

    Returns:
        Any: The processed event
    """
    logger.info(f"Processing event: {event}")

    if isinstance(event, ThreadRunCreated):
        logger.info("Assistant is thinking...")
        yield "", AssistantMessageDeltaType.MESSAGE_START

    elif isinstance(event, ThreadMessageCreated):
        # Set the current message ID
        logger.info(f"New message created: {event.data.id=}")
        current_message_id.set(event.data.id)

    elif isinstance(event, ThreadRunInProgress):
        logger.info("Processing your request...")
        yield "", AssistantMessageDeltaType.METADATA

    elif isinstance(event, ThreadMessageDelta):
        data = event.data.delta.content
        for d in data:
            yield d.text.value, AssistantMessageDeltaType.CONTENT_BLOCK

    elif isinstance(event, ThreadRunQueued):
        logger.info("Request queued...")

    elif isinstance(event, ThreadRunRequiresAction):
        run = event.data
        tool_outputs = await _process_assistant_tool_calls(
            tool_calls=run.required_action.submit_tool_outputs.tool_calls, tools=tools, **kwargs
        )
        tool_output_events = await async_openai_client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs, stream=True
        )
        async for tool_event in tool_output_events:
            async for token in _process_assistant_event(tool_event, thread=thread, tools=tools, **kwargs):
                yield token

    elif isinstance(event, ThreadRunCompleted):
        logger.info("Assistant finished processing your request.")
        yield "", AssistantMessageDeltaType.MESSAGE_END

    elif any(
        isinstance(event, cls)
        for cls in [
            ThreadRunFailed,
            ThreadRunCancelling,
            ThreadRunCancelled,
            ThreadRunExpired,
            ThreadRunStepFailed,
            ThreadRunStepCancelled,
        ]
    ):
        raise Exception("Run failed")  # pylint: disable=broad-exception-raised

    else:
        logger.warning(f"Unhandled Assistant event: {event}")


async def save_assistant_user_message(
    thread_id: str,
    content: str,
) -> Message:
    """
    Save the assistant user message.

    Args:
        thread_id (str): The ID of the chat thread
        content (str): The content of the message

    Returns:
        None
    """

    thread_message: Message = await async_openai_client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=content
    )
    logger.info(f"Created a message in Assistants API: {thread_message=}, {thread_id=}.")

    return thread_message


async def get_assistant_response__async(
    assistant_id: str,
    thread_message: Message,
    thread_id: str,
    functions: dict[str, Callable],
    **kwargs: dict[str, Any],
) -> AsyncGenerator[Tuple[str, AssistantMessageDeltaType], None]:
    """
    Get the assistant response.

    Args:
        assistant_id (str): The ID of the assistant to use
        thread_message (Message): The prompt to send to the assistant
        thread_id (str): The ID of the chat thread
        functions (dict[str, callable]): The functions to execute
        **kwargs (dict[str, Any]): The keyword arguments to pass to the functions

    Yields:
        str: Status updates and the final response from the assistant
    """

    logger.info(f"Getting the Assistant response for {thread_message.content=}...")

    # TODO: [2025-01-29 by Mykola] Allow different assistants to be chosen by the user and/or depending on the use-case
    assistant = await async_openai_client.beta.assistants.retrieve(assistant_id)

    thread = await async_openai_client.beta.threads.retrieve(thread_id)

    # TODO: [2025-01-31 by Mykola] Stop all the active runs for the thread before creating a new one
    try:
        async with async_openai_client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=assistant.id,
            # max_prompt_tokens=settings.OPENAI_MAX_PROMPT_TOKENS,
            # max_completion_tokens=settings.OPENAI_MAX_COMPLETION_TOKENS,
        ) as stream:
            logger.info(f"Stream the thread with: {thread_message=}, {thread_id=}. Got {stream=}")

            async for event in stream:
                logger.info(f"Got an Assistant event: {event.event}")

                async for yielded_event in _process_assistant_event(event, thread=thread, tools=functions, **kwargs):
                    yield yielded_event

    except Exception as e:
        error_message = f"Error processing assistant response: {str(e)}"
        logger.error(error_message)
        yield f"\nError: {error_message}", AssistantMessageDeltaType.ERROR

        # Attempt to cancel the run if an exception occurs
        try:
            await async_openai_client.beta.threads.runs.cancel(
                thread_id=thread.id,
                run_id=stream.current_run.id,
            )
        except Exception as cancel_error:
            logger.error(f"Failed to cancel run after error: {str(cancel_error)}")
