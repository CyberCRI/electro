"""The API server that works as an endpoint for all the Electro Interfaces."""

from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from tortoise.contrib.fastapi import register_tortoise

from .authentication import authenticate_user
from .interfaces import APIInterface, WebSocketInterface
from .models import Message, PlatformId, User
from .toolkit.tortoise_orm import get_tortoise_config
from .utils import format_historical_message, paginate_response

app = FastAPI(
    title="Electro API",
    description="The API server that works as an endpoint for all the Electro Interfaces.",
    version="0.1.0",
    # docs_url="/",
    # redoc_url=None,
)


@app.get("/api/platform/{platform}/user/{user_platform_id}")
async def get_user(platform: str, user_id: str, request_user: Optional[User] = Depends(authenticate_user)):
    """
    Test the API endpoint.
    """
    platform_id = await PlatformId.get_or_none(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if not platform_id:
        raise HTTPException(status_code=404, detail="User not found.")
    user = await platform_id.user
    # TODO: create a permission check to allow access to other users
    if request_user == user:
        return {
            "id": user.id,
            "username": user.username,
            "platform_ids": [
                {
                    "platform": platform.platform,
                    "platform_id": platform.platform_id,
                    "type": platform.type,
                }
                for platform in await user.platform_ids.all()
            ],
        }
    raise HTTPException(status_code=403, detail="You are not authorized to access this user's information.")


@app.get("/api/platform/{platform}/user/{user_id}/messages")
async def get_user_messages(
    platform: str,
    user_id: str,
    request_user: Optional[User] = Depends(authenticate_user),
    limit: int = 20,
    offset: int = 0,
):
    """
    Get the message history for a user.

    Arguments:
        user: The user whose message history is to be retrieved.
        limit: The maximum number of messages to retrieve.
        offset: The number of messages to skip before retrieving the history.
    """
    platform_id = await PlatformId.get_or_none(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if not platform_id:
        raise HTTPException(status_code=404, detail="User not found.")
    user = await platform_id.user
    if request_user == user:
        messages = Message.filter(user=user, is_temporary=False, is_command=False).order_by("-date_added")
        return await paginate_response(
            messages,
            format_historical_message,
            limit=limit,
            offset=offset,
            url=f"/api/platform/{platform}/user/{user_id}/messages",
        )
    raise HTTPException(status_code=403, detail="You are not authorized to access this user's message history.")


@app.post("/api/platform/{platform}/user/{user_id}/messages")
async def process_message(
    platform: str,
    user_id: str,
    data: Dict[str, Any],
    request_user: Optional[User] = Depends(authenticate_user),
):
    """Process the message."""
    platform_id = await PlatformId.get_or_none(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if not platform_id:
        raise HTTPException(status_code=404, detail="User not found.")
    user = await platform_id.user
    if request_user == user:
        interface = APIInterface()
        await interface.handle_incoming_action(user, platform, data)
        return interface.messages.get()
    raise HTTPException(status_code=403, detail="You are not authorized to send messages on behalf of this user.")


@app.websocket("/websocket/platform/{platform}/user/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    platform: str,
    user_id: str,
    request_user: Optional[User] = Depends(authenticate_user),
):
    """Handle the websocket connection."""
    platform_id = await PlatformId.get_or_none(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if not platform_id:
        raise HTTPException(status_code=404, detail="User not found.")
    user = await platform_id.user
    if request_user == user:
        interface = WebSocketInterface()
        await interface.connect(websocket)
        try:
            while websocket.application_state == WebSocketState.CONNECTED:
                data = await websocket.receive_json()
                await interface.handle_incoming_action(user, platform, data)
        except WebSocketDisconnect:
            await interface.disconnect()
    raise HTTPException(status_code=403, detail="You are not authorized to send messages on behalf of this user.")


# region Register Tortoise
register_tortoise(app, config=get_tortoise_config())

# endregion
