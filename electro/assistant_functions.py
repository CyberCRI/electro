"""Functions for OpenAI Assistant."""

import json
from contextvars import ContextVar

from .enums import FrontendAction
from .toolkit.loguru_logging import logger

# Create a ContextVar to store frontend actions
action_context: ContextVar[list[str]] = ContextVar("actions", default=[])


async def get_frontend_actions(*_, **__) -> str:
    """
    Asynchronously fetches the list of frontend actions from the database.
    This function is designed to work directly with OpenAI Assistant's tool calling pattern.

    Returns:
        str: JSON string containing the list of frontend actions or error information

    Schema:
    {
        "name": "get_frontend_actions",
        "description": "Fetch the list of the actions that can be performed by the frontend",
        "parameters": {
            "type": "object",
            "required": [],
            "properties": {}
        }
    }
    """
    try:
        # Fetch the list of frontend actions
        frontend_actions = [action.value for action in FrontendAction]

        # Return the list of frontend actions
        return json.dumps(frontend_actions, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Unexpected error while fetching frontend actions: {str(e)}")
        error_response = {"error": str(e), "status": "failed"}
        return json.dumps(error_response, ensure_ascii=False, indent=2)


async def submit_frontend_action(action: str, *_, **__) -> str:
    """
    Asynchronously submits a frontend action to the database.
    This function is designed to work directly with OpenAI Assistant's tool calling pattern.

    Args:
        action (str): The frontend action to submit

    Returns:
        str: JSON string containing the result or error information

    Schema:
    {
        "name": "submit_frontend_action",
        "description": "Submit an action to be performed by the frontend",
        "parameters": {
            "type": "object",
            "required": ["action"],
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The frontend action to submit"
                }
            }
        }
    }
    """
    try:
        # Input validation
        if not action or not isinstance(action, str):
            error_response = {"error": "action must be a non-empty string", "status": "failed"}
            return json.dumps(error_response, ensure_ascii=False, indent=2)

        # Check if the action is valid
        if action not in [frontend_action.value for frontend_action in FrontendAction]:
            error_response = {"error": "Invalid frontend action", "status": "failed"}
            return json.dumps(error_response, ensure_ascii=False, indent=2)

        # Save the frontend action
        # TODO: [2025-01-31 by Mykola] Check if we can `.append()` it in-place, or we need to `.get()` and `.set()` it
        action_context.get().append(action)

        return json.dumps({"status": "success"}, ensure_ascii=False, indent=2)

    except Exception as exception:
        logger.error(f"Error submitting frontend action: {exception}")
        error_response = {"error": str(exception), "status": "failed"}
        return json.dumps(error_response, ensure_ascii=False, indent=2)
