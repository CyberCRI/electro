from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from .models import BotMessage, Button, File
from .toolkit.loguru_logging import logger


class BaseInterface(ABC):
    """
    Interface class for the Electro framework."""

    async def format_message(
        self,
        message: BotMessage,
        buttons: Optional[List[Button]] = None,
        files: Optional[List[File]] = None,
    ) -> Dict[str, Any]:
        """
        Format the message to be sent to the client.
        """
        return {
            "id": message.id,
            "receiver": (
                {
                    "id": message.receiver.id,
                    "username": message.receiver.username,
                    "platform_ids": {
                        identifier.platform: identifier.platform_id
                        for identifier in await message.receiver.platform_ids.all()
                    },
                }
                if message.receiver
                else None
            ),
            "channel": (
                {
                    "id": message.channel.id,
                    "name": message.channel.name,
                    "platform_ids": {
                        identifier.platform: identifier.platform_id
                        for identifier in await message.channel.platform_ids.all()
                    },
                }
                if message.channel
                else None
            ),
            "content": message.content,
            "files": [],
            "buttons": [
                {
                    "id": button.id,
                    "custom_id": button.custom_id,
                    "style": button.style,
                    "label": button.label,
                    "clicked": button.clicked,
                    "remove_after_click": button.remove_after_click,
                }
                for button in buttons or []
            ],
        }

    @abstractmethod
    async def send_message(self, message: BotMessage, buttons: Optional[Button] = None, files: Optional[File] = None):
        raise NotImplementedError

    @abstractmethod
    async def stop_process(self, *args, **kwargs):
        raise NotImplementedError


class WebSocketInterface(BaseInterface):
    """
    WebSocket Interface for the Electro framework.

    On the server side, the WebSocketInterface is used to send messages to the client,
    If you want to send a message to the client in a Flow, you can use the `send_message` method.
    """

    def __init__(self):
        self.interface: WebSocket | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.interface = websocket

    async def disconnect(self):
        await self.interface.close()
        self.interface = None

    async def send_message(self, message: BotMessage, buttons: Optional[Button] = None, files: Optional[File] = None):
        data = await self.format_message(message, buttons, files)
        await self.interface.send_json(data)

    async def stop_process(self, code: int = 1000, reason: Optional[str] = None):
        await self.interface.close(code, reason)


class APIInterface(BaseInterface):
    def __init__(self):
        self.messages = []

    async def send_message(self, message: BotMessage, buttons: Optional[Button] = None, files: Optional[File] = None):
        data = await self.format_message(message, buttons, files)
        self.messages.append(data)

    async def stop_process(self, *args, **kwargs):
        return self.messages
