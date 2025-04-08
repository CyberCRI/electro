"""Decorators used in the Application."""

from functools import wraps
from typing import Callable, Coroutine

from electro.flow_connector import FlowConnector, FlowConnectorEvents


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
