"""The API server that works as an endpoint for all the Electro Interfaces."""

from typing import Any, Dict, Optional

# from fastapi import Depends
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from tortoise.contrib.fastapi import register_tortoise

from .enums import SupportedPlatforms
from .interfaces import APIInterface, WebSocketInterface
from .models import Channel, Message, User
from .settings import settings
from .toolkit.tortoise_orm import get_tortoise_config
from .utils import format_historical_message


def validate_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Validate the API key provided in the request header."""
    if not x_api_key and settings.API_KEY:
        raise HTTPException(status_code=401, detail="API Key is missing")
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


app = FastAPI(
    title="Electro API",
    description="The API server that works as an endpoint for all the Electro Interfaces.",
    version="0.1.0",
    # dependencies=[Depends(validate_api_key)],
    # docs_url="/",
    # redoc_url=None,
)


@app.get("/api/platform/{platform}/user/{user_id}/messages")
async def get_user_messages(user_id: str, limit: int = 20, offset: int = 0):
    """
    Get the message history for a user.

    Arguments:
        user: The user whose message history is to be retrieved.
        limit: The maximum number of messages to retrieve.
        offset: The number of messages to skip before retrieving the history.
    """
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    messages = (
        await Message.filter(
            user=user,
            is_temporary=False,
        )
        .order_by("-date_added")
        .limit(limit)
        .offset(offset)
    )
    return [await format_historical_message(message) for message in messages]


@app.get("/api/channel/{channel_id}/messages")
async def get_channel_messages(channel_id: str, limit: int = 20, offset: int = 0):
    """
    Get the message history for a channel.

    Arguments:
        channel: The channel whose message history is to be retrieved.
        limit: The maximum number of messages to retrieve.
        offset: The number of messages to skip before retrieving the history.
    """
    channel = await Channel.get_or_none(id=channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    messages = (
        await Message.filter(
            channel=channel,
            is_temporary=False,
        )
        .order_by("-date_added")
        .limit(limit)
        .offset(offset)
    )
    return [await format_historical_message(message) for message in messages]


@app.post("/api/platform/{platform}")
async def process_message(platform: str, data: Dict[str, Any]):
    """Process the message."""
    if platform not in SupportedPlatforms:
        raise ValueError(f"Platform {platform} is not supported.")
    interface = APIInterface()
    await interface.handle_incoming_action(platform, data)
    return interface.messages.get()


@app.websocket("/websocket/platform/{platform}/user/{user_id}")
async def websocket_endpoint(websocket: WebSocket, platform: str, user_id: str):  # pylint: disable=W0613
    if platform not in SupportedPlatforms:
        raise ValueError(f"Platform {platform} is not supported.")
    interface = WebSocketInterface()
    await interface.connect(websocket)
    try:
        while websocket.application_state == WebSocketState.CONNECTED:
            data = await websocket.receive_json()
            await interface.handle_incoming_action(platform, data)
    except WebSocketDisconnect:
        await interface.disconnect()


# region Register Tortoise
register_tortoise(app, config=get_tortoise_config())

# endregion
