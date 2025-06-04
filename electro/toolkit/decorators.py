"""Decorators used in the Application."""

from asyncio import Lock
from collections import defaultdict
from functools import wraps
from typing import Callable, Coroutine

from electro.exceptions import EventCannotBeProcessed
from electro.flow_connector import FlowConnector, FlowConnectorEvents
from electro.models import Channel, Message
from electro.settings import settings
from electro.toolkit.i18n_gettext import _
from electro.toolkit.loguru_logging import logger
from electro.toolkit.templated_i18n import TemplatedString


def with_constant_typing(
    run_only_on_events: list[FlowConnectorEvents] | None = None,
) -> Callable:
    """Send a typing indicator while executing the function."""

    def decorator(function: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        """The actual decorator."""

        @wraps(function)
        async def wrapper(*args, **kwargs):
            # Check if any of the arguments is a FlowConnector
            flow_connector: FlowConnector | None = next(
                (arg for arg in args if isinstance(arg, FlowConnector)),
                None,
            )

            if flow_connector and (not run_only_on_events or flow_connector.event in run_only_on_events):
                # Send a typing indicator while executing the function
                async with flow_connector.interface.with_constant_typing(flow_connector.user, flow_connector.channel):
                    return await function(*args, **kwargs)

            # If the FlowConnector is not found, just execute the function
            return await function(*args, **kwargs)

        return wrapper

    return decorator


def fail_safely(function: Callable[..., Coroutine]):
    """Fail safely and send the message to the User about the issue"""

    @wraps(function)
    async def wrapper(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except Exception as exception:
            # Log the exception with the traceback
            logger.exception(exception)

            # Check if any of the arguments is a FlowConnector
            flow_connector: FlowConnector | None = next(
                (arg for arg in args if isinstance(arg, FlowConnector)),
                None,
            )

            substitute_dict = {
                "function_name": function.__name__,
                "exception": exception,
                "exception_type": type(exception),
                "exception_text": str(exception),
                "user_id": flow_connector.user.id if flow_connector else "N/A",
                "user_name": flow_connector.user.username if flow_connector else "N/A",
            }

            if flow_connector:
                if isinstance(exception, EventCannotBeProcessed):
                    error_text__template = _("fail_safely.error_text.event_cannot_be_processed")
                    error_text__template__debug = _("fail_safely.error_text.event_cannot_be_processed.debug")
                else:
                    error_text__template = _("fail_safely.error_text")
                    error_text__template__debug = _("fail_safely.error_text.debug")

                # Send a message to the user about the issue and delete after 20 seconds
                if settings.DEBUG:
                    error_text = error_text__template__debug.safe_substitute(**substitute_dict)
                else:
                    error_text = error_text__template.safe_substitute(**substitute_dict)
                # Set delete_after=20 to delete the message after 20 seconds
                await flow_connector.interface.send_error(error_text, flow_connector.user, flow_connector.channel)
            else:
                logger.error(f"FlowConnector is not set for the function: {function.__name__} in {args=}")

            if not (
                global_errors_channel_obj := await Channel.get_or_none(used_for=Channel.ChannelUsedFor.GLOBAL_ERRORS)
            ):
                logger.error("Global errors channel is not set.")
                raise exception

            if settings.DEBUG:
                message = _("fail_safely.global_error_text.debug").safe_substitute(**substitute_dict)
            else:
                message = _("fail_safely.global_error_text").safe_substitute(**substitute_dict)
            await Message.create(
                is_bot_message=True,
                channel=global_errors_channel_obj,
                content=message,
            )
            # Re-raise the exception after handling
            raise exception

    return wrapper


GLOBAL_USER_LOCKS: defaultdict[int, Lock] = defaultdict(Lock)


def forbid_concurrent_execution(
    keep_extra_messages=False,
    extra_messages_reply: TemplatedString | None = _("forbidden_concurrent_execution.extra_messages_reply"),
) -> Callable:
    """Forbid concurrent execution of the function for the same User."""

    def decorator(function: Callable[..., Coroutine]):
        """The actual decorator."""

        @wraps(function)
        async def wrapper(*args, **kwargs):
            # Get the `FlowConnector` from the arguments
            flow_connector: FlowConnector | None = next(
                (arg for arg in args if isinstance(arg, FlowConnector)),
                None,
            )

            if not flow_connector:
                logger.error(f"FlowConnector is not set for the function: {function.__name__} in {args=}")
                return await function(*args, **kwargs)

            # Get the User's ID
            user_id = flow_connector.user.id
            # Get the User's lock
            user_lock = GLOBAL_USER_LOCKS[user_id]

            # Check if the User's lock is already acquired
            if user_lock.locked() and not keep_extra_messages:
                if flow_connector.message:
                    # Send a message to the User saying that the function is already running
                    delete_after = 12 if not keep_extra_messages else None
                    await flow_connector.interface.send_message(
                        extra_messages_reply, flow_connector.user, flow_connector.channel, delete_after=delete_after
                    )
                else:
                    logger.warning(f"Extra messages are not allowed for the function: {function.__name__} in {args=}")
            else:
                # With the lock acquired, execute the function
                async with user_lock:
                    return await function(*args, **kwargs)

        return wrapper

    return decorator
