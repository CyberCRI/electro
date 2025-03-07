from typing import Dict, Optional

from fastapi import WebSocket

from .toolkit.loguru_logging import logger


class Interface:
    async def send_json(self, *args, **kwargs):
        raise NotImplementedError

    async def stop_process(self, *args, **kwargs):
        raise NotImplementedError


class WebSocketInterface(Interface):
    """
    WebSocket Interface for the Electro framework.

    On the server side, the WebSocketInterface is used to send messages to the client,
    If you want to send a message to the client in a Flow, you can use the `send_json` method.
    """

    def __init__(self):
        self.interface: WebSocket | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.interface = websocket

    async def disconnect(self):
        await self.interface.close()
        self.interface = None

    async def send_json(self, data: Dict[str, str]):
        await self.interface.send_json(data)

    async def stop_process(self, code: int = 1000, reason: Optional[str] = None):
        await self.interface.close(code, reason)


class APIInterface(Interface):
    def __init__(self):
        self.messages = []

    async def send_json(self, data: Dict[str, str]):
        self.messages.append(data)

    async def stop_process(self, *args, **kwargs):
        return self.messages
