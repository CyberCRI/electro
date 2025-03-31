"""The API server that works as an endpoint for all the Electro Interfaces."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from tortoise.contrib.fastapi import register_tortoise

from .enums import SupportedPlatforms
from .flow_connector import FlowConnectorEvents
from .flow_manager import global_flow_manager
from .interfaces import APIInterface, WebSocketInterface
from .schemas import ButtonClick, ReceivedMessage
from .toolkit.tortoise_orm import get_tortoise_config

app = FastAPI(
    title="Electro API",
    description="The API server that works as an endpoint for all the Electro Interfaces.",
    version="0.1.0",
    # docs_url="/",
    # redoc_url=None,
)


@app.post("/message/platform/{platform}/")
async def process_message(message: ReceivedMessage, platform: str):
    """Process the message."""
    if platform not in SupportedPlatforms:
        raise ValueError(f"Platform {platform} is not supported.")
    interface = APIInterface()
    return await global_flow_manager.on_message(platform, message, interface)


@app.websocket("/websocket/platform/{platform}/user/{user_id}")
async def websocket_endpoint(websocket: WebSocket, platform: str, user_id: str):
    if platform not in SupportedPlatforms:
        raise ValueError(f"Platform {platform} is not supported.")
    interface = WebSocketInterface()
    await interface.connect(websocket)
    try:
        while websocket.application_state == WebSocketState.CONNECTED:
            data = await websocket.receive_json()
            action = data.get("action")
            content = data.get("content")
            if action == FlowConnectorEvents.MESSAGE:
                content = ReceivedMessage.model_validate(content)
                await global_flow_manager.on_message(platform, content, interface)
            if action == FlowConnectorEvents.BUTTON_CLICK:
                content = ButtonClick.model_validate(content)
                await global_flow_manager.on_button_click(platform, content, interface)
            if action == FlowConnectorEvents.MEMBER_JOIN:
                pass
            if action == FlowConnectorEvents.MEMBER_UPDATE:
                pass
    except WebSocketDisconnect:
        await interface.disconnect()


# region Register Tortoise
register_tortoise(app, config=get_tortoise_config())

# endregion
