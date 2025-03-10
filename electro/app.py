"""The API server that works as an endpoint for all the Electro Interfaces."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from tortoise.contrib.fastapi import register_tortoise

from . import types_ as types
from .flow_manager import global_flow_manager
from .interfaces import APIInterface, WebSocketInterface
from .toolkit.tortoise_orm import get_tortoise_config

app = FastAPI(
    title="Electro API",
    description="The API server that works as an endpoint for all the Electro Interfaces.",
    version="0.1.0",
    # docs_url="/",
    # redoc_url=None,
)

api_app = app
websocket_app = app


@api_app.post("/message")
async def process_message(message: types.Message) -> types.MessageToSend | None:
    """Process the message."""
    manager = APIInterface()
    return await global_flow_manager.on_message(message, manager)


@websocket_app.websocket("/websocket/client/{client_name}/user/{user_id}")
async def websocket_endpoint(websocket: WebSocket, client_name: str, user_id: str):
    manager = WebSocketInterface()
    await manager.connect(websocket)
    try:
        while websocket.application_state == WebSocketState.CONNECTED:
            data = await websocket.receive_json()
            data = types.Message.model_validate(data)
            await global_flow_manager.on_message(data, manager)
    except WebSocketDisconnect:
        await manager.disconnect()


# region Register Tortoise
register_tortoise(api_app, config=get_tortoise_config())
register_tortoise(websocket_app, config=get_tortoise_config())

# endregion
