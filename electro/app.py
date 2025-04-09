"""The API server that works as an endpoint for all the Electro Interfaces."""

from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from tortoise.contrib.fastapi import register_tortoise

from .enums import SupportedPlatforms
from .interfaces import APIInterface, WebSocketInterface
from .settings import settings
from .toolkit.tortoise_orm import get_tortoise_config


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
    dependencies=[Depends(validate_api_key)],
    # docs_url="/",
    # redoc_url=None,
)


@app.post("/api/platform/{platform}")
async def process_message(platform: str, data: Dict[str, Any]):
    """Process the message."""
    if platform not in SupportedPlatforms:
        raise ValueError(f"Platform {platform} is not supported.")
    interface = APIInterface()
    await interface.handle_incoming_action(platform, data)
    return interface.messages.get()


@app.websocket("/websocket/platform/{platform}/user/{user_id}")
async def websocket_endpoint(websocket: WebSocket, platform: str, user_id: str):
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
