"""The API server that works as an endpoint for all the Electro Interfaces."""

from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketState
from tortoise.contrib.fastapi import register_tortoise

from .authentication import authenticate_user
from .interfaces import APIInterface, WebSocketInterface
from .models import Message, PlatformId, User
from .schemas import CookieToken
from .toolkit.tortoise_orm import get_tortoise_config
from .utils import format_historical_message, limit_from_id_paginate_response

app = FastAPI(
    title="Electro API",
    description="The API server that works as an endpoint for all the Electro Interfaces.",
    version="0.1.0",
    # docs_url="/",
    # redoc_url=None,
)

# CORS

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.patch("/api/platforms/{platform}/user/{user_id}")
async def update_user(
    platform: str,
    user_id: str,
    data: Dict[str, Any],
    request_user: Optional[User] = Depends(authenticate_user),
):
    """
    Update the user information.

    Arguments:
        platform: The platform where the user is registered.
        user_id: The ID of the user on the platform.
        username: Optional username to set for the user.
    """
    platform_id = await PlatformId.get_or_none(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if not platform_id:
        raise HTTPException(status_code=404, detail="User not found.")
    user: User = await platform_id.user
    if request_user == user:
        if "username" in data:
            user.username = data["username"]
            await user.save()
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
    raise HTTPException(status_code=403, detail="You are not authorized to update this user's information.")


@app.get("/api/platform/{platform}/user/{user_id}")
async def get_user(platform: str, user_id: str, request_user: Optional[User] = Depends(authenticate_user)):
    """
    Test the API endpoint.
    """
    platform_id = await PlatformId.get_or_none(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if not platform_id:
        raise HTTPException(status_code=404, detail="User not found.")
    user: User = await platform_id.user
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
    from_id: Optional[int] = None,
):
    """
    Get the message history for a user.

    Arguments:
        user: The user whose message history is to be retrieved.
        limit: The maximum number of messages to retrieve.
        offset: The number of messages to skip before retrieving the history.
        from_id: If provided, this will override the offset to start from the latest message ID.
    """
    platform_id = await PlatformId.get_or_none(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if not platform_id:
        raise HTTPException(status_code=404, detail="User not found.")
    user = await platform_id.user
    if request_user == user:
        messages = Message.filter(user=user, is_temporary=False).order_by("-date_added")
        return await limit_from_id_paginate_response(
            messages,
            format_historical_message,
            limit=limit,
            from_id=from_id,
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


@app.post("/api/cookies")
async def set_cookie(data: CookieToken, response: Response):
    cookie_value = "" if data.token is None else data.token
    response.set_cookie(key="Authorization", value=cookie_value)
    return {"status": "ok"}


# region Register Tortoise
register_tortoise(app, config=get_tortoise_config())

# endregion
