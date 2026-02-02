"""The Chat Router."""

from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import StreamingResponse

from .assistant_functions import action_context, get_frontend_actions, submit_frontend_action
from .auth_dependencies import get_current_user
from .enums import AssistantType, FrontendAction
from .helpers import (
    create_new_chat_thread,
    current_message_id,
    get_assistant_response,
    get_assistant_response__async,
    save_assistant_user_message,
)
from .models import Assistant, AssistantChatMessage, AssistantChatThread, User
from .schemas import (
    AssistantChatMessageCreateSchema,
    AssistantChatMessageDeltaSchema,
    AssistantChatMessageSchema,
    AssistantChatThreadCreateSchema,
    AssistantChatThreadSchema,
)
from .toolkit.loguru_logging import logger

chat__router = APIRouter(tags=["Chat"], dependencies=[Depends(get_current_user)])


ENABLED_FUNCTIONS = {
    "get_frontend_actions": get_frontend_actions,
    "submit_frontend_action": submit_frontend_action,
}


async def _get_thread(thread_id: str, user: User) -> AssistantChatThread:
    """
    Ensure that the user has ownership of the chat thread.

    Args:
        thread_id (str): The `.thread_id` of the chat thread
        user (User): The current user

    Returns:
        AssistantChatThread: The chat thread object if the user has ownership
    """
    if not (thread := await AssistantChatThread.get_or_none(thread_id=thread_id).prefetch_related("user", "assistant")):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No chat thread found with ID {thread_id}",
        )

    if not thread.user == user and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this chat thread",
        )

    return thread


async def _validate_message(message: AssistantChatMessageCreateSchema) -> AssistantChatMessageCreateSchema:
    """
    Validate the message before saving it.

    Args:
        message (AssistantChatMessageCreateSchema): The message to validate

    Raises:
        HTTPException: If the message is invalid
    """
    if not message.role or message.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The message role must be 'user'",
        )

    if not message.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The message content cannot be empty",
        )

    return message


# region Chat Endpoints
@chat__router.get("/threads")
async def get_chat_threads(
    assistant_type: AssistantType | None = None, user: User = Depends(get_current_user)
) -> list[AssistantChatThreadSchema]:
    """
    Get the list of chat threads.

    Args:
        assistant_type (AssistantType | None): The type of the chat thread (optional)
        user (User): The current user

    Returns:
        Dict containing the list of chat threads
    """
    assistant_chats__query = AssistantChatThread.filter(user=user).prefetch_related("assistant")

    if assistant_type:
        assistant_chats__query = assistant_chats__query.filter(assistant__assistant_type=assistant_type)

    assistant_chat_threads = [
        AssistantChatThreadSchema.model_validate(thread) for thread in await assistant_chats__query
    ]

    return assistant_chat_threads


@chat__router.post("/threads")
async def create_chat_thread(
    thread: AssistantChatThreadCreateSchema,
    user: User = Depends(get_current_user),
) -> AssistantChatThreadSchema:
    """
    Create a chat thread.

    Args:
        thread (AssistantChatThreadCreateSchema): The chat thread to create
        user (User): The current user

    Returns:
        Dict containing the created chat thread
    """
    if not (
        assistant := await Assistant.filter(assistant_type=thread.assistant_type, is_active=True, is_deleted=False)
        .order_by("-date_added")
        .first()
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active assistant found with type {thread.assistant_type}",
        )

    try:
        created_thread = await create_new_chat_thread()
    except Exception as exception:
        logger.error(f"Error creating chat thread: {exception}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating chat thread",
        )

    thread__obj = await AssistantChatThread.create(
        user=user,
        assistant=assistant,
        thread_id=created_thread.id,
        **thread.model_dump(exclude_unset=True, exclude={"assistant_type"}),
    )

    return AssistantChatThreadSchema.model_validate(thread__obj)


@chat__router.get("/{thread_id}/messages")
async def get_chat_thread_messages(
    thread_id: str, approved_user: User = Depends(get_current_user)
) -> list[AssistantChatMessageSchema]:
    """
    Get the messages of the chat thread with the given ID.

    Args:
        thread_id (str): The `.thread_id` of the chat thread
        approved_user (User): The current approved user

    Returns:
        Dict containing the messages of the chat thread
    """
    thread = await _get_thread(thread_id, approved_user)

    return [
        AssistantChatMessageSchema.model_validate(message)
        for message in await AssistantChatMessage.filter(thread=thread)
    ]


@chat__router.post("/{thread_id}/messages")
async def create_chat_thread_message(
    thread_id: str, message: AssistantChatMessageCreateSchema, approved_user: User = Depends(get_current_user)
) -> list[AssistantChatMessageSchema]:
    """
    Create a message in the chat thread with the given ID.

    Args:
        thread_id (str): The `.thread_id` of the chat thread
        message (AssistantChatMessageCreateSchema): The message to create
        approved_user (User): The current user

    Returns:
        Dict containing the created message
    """
    thread = await _get_thread(thread_id, approved_user)

    message = await _validate_message(message)

    # Save the user message as a message
    user_message = await AssistantChatMessage.create(thread=thread, **message.model_dump(exclude_unset=True))
    logger.info(f"User message saved: {user_message}")

    # Reset the frontend actions context for this request
    action_context.set([])

    # TODO: [2025-07-10 by Mykola] Allow getting multiple messages from the Assistant
    assistant_response = await get_assistant_response(
        assistant_id=thread.assistant.id,
        prompt=message.content,
        thread_id=thread_id,
        functions=ENABLED_FUNCTIONS,
        approved_user=approved_user,
    )
    logger.info(f"Assistant response: {assistant_response}")

    # Save the assistant response as a message
    assistant_message = await AssistantChatMessage.create(thread=thread, content=assistant_response, role="assistant")
    logger.info(f"Assistant message saved: {assistant_message}")

    # TODO: [2025-07-14 by Mykola] Make it non-ugly
    assistant_message.frontend_actions = action_context.get()

    return [
        # TODO: [2025-07-14 by Mykola] Allow getting multiple messages from the Assistant
        AssistantChatMessageSchema.model_validate(assistant_message)
    ]


async def create_chat_thread_message__streaming(
    thread_id: str, message: AssistantChatMessageCreateSchema, approved_user: User = Depends(get_current_user)
) -> AsyncIterator[AssistantChatMessageDeltaSchema]:
    """
    Create a message in the chat thread with the given ID.

    Args:
        thread_id (str): The `.thread_id` of the chat thread
        message (AssistantChatMessageCreateSchema): The message to create
        approved_user (User): The current user

    Returns:
        StreamingResponse: The created message as a stream
    """
    thread = await _get_thread(thread_id, approved_user)

    message = await _validate_message(message)

    # Save the user message as a message
    user_message = await AssistantChatMessage.create(thread=thread, **message.model_dump(exclude_unset=True))
    logger.info(f"User message saved: {user_message}")

    # Reset the frontend actions context for this request
    action_context.set([])
    # Set the current message ID to the user message ID
    current_message_id.set(None)

    user_thread_message = await save_assistant_user_message(
        thread_id=thread.thread_id,
        content=message.content,
    )

    # Save the message_id from the `user_thread_message`
    user_message.message_id = user_thread_message.id
    await user_message.save()

    all_content_blocks = []
    async for message_block, assistant_message_delta_type in get_assistant_response__async(
        assistant_id=thread.assistant.id,
        thread_message=user_thread_message,
        thread_id=thread_id,
        functions=ENABLED_FUNCTIONS,
        approved_user=approved_user,
    ):
        logger.info(f"Assistant response: {message_block}")
        all_content_blocks.append(message_block)

        # frontend_actions: list[str] = action_context.get()
        # if frontend_actions:
        #     yield AssistantChatMessageDeltaSchema(
        #         role="assistant",
        #         content=message_block,
        #         type=AssistantMessageDeltaType.CONTENT_BLOCK,
        #     )

        frontend_actions: list[str] = action_context.get()

        yield AssistantChatMessageDeltaSchema(
            message_id=current_message_id.get(),
            role="assistant",
            content=message_block,
            type=assistant_message_delta_type,
            frontend_actions=[FrontendAction(action) for action in frontend_actions],
        )

        # Reset the frontend actions context for the next message
        if frontend_actions:
            action_context.set([])

    # Save the assistant response as a message
    assistant_message = await AssistantChatMessage.create(
        thread=thread, content="".join(all_content_blocks), role="assistant", message_id=current_message_id.get()
    )
    logger.info(f"Assistant message saved: {assistant_message}")

    # Reset the current message ID
    current_message_id.set(None)


async def assistant_delta_messages_to_sse(
    assistant_delta_messages: AsyncIterator[AssistantChatMessageDeltaSchema],
) -> AsyncIterator[str]:
    """
    Convert the assistant delta messages to Server-Sent Events.

    Args:
        assistant_delta_messages (AsyncIterator[AssistantChatMessageDeltaSchema]): The assistant delta messages

    Returns:
        AsyncIterator[str]: The Server-Sent Events
    """
    async for assistant_delta_message in assistant_delta_messages:
        yield f"data: {assistant_delta_message.model_dump_json()}\n\n"


@chat__router.post("/{thread_id}/messages/stream")
async def create_chat_thread_message_streaming(
    thread_id: str, message: AssistantChatMessageCreateSchema, approved_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    Create a message in the chat thread with the given ID.

    Args:
        thread_id (str): The `.thread_id` of the chat thread
        message (AssistantChatMessageCreateSchema): The message to create
        approved_user (User): The current user

    Returns:
        StreamingResponse: The created message as a stream
    """
    return StreamingResponse(
        assistant_delta_messages_to_sse(create_chat_thread_message__streaming(thread_id, message, approved_user)),
        media_type="text/event-stream",
    )


@chat__router.delete("/{thread_id}")
async def delete_chat_thread(thread_id: str, superuser_user: User = Depends(get_current_user)) -> dict:
    """
    Delete a chat thread by its thread_id.

    Args:
        thread_id (str): The `.thread_id` of the chat thread to delete
        superuser_user (User): The current superuser user

    Returns:
        dict: Confirmation message
    """
    thread = await _get_thread(thread_id, superuser_user)

    await AssistantChatMessage.filter(thread=thread).delete()
    await thread.delete()

    return {"message": "Chat thread deleted successfully"}
