from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union

from fastapi import WebSocket

from .enums import ResponseTypes
from .models import BotMessage, Button, Channel, File, Guild, Role, User
from .toolkit.images_storage.universal_image_storage import universal_image_storage

if TYPE_CHECKING:
    from .contrib.buttons import ActionButton


class BaseInterface(ABC):
    """
    Interface class for the Electro framework.
    """

    async def _format_buttons(self, buttons: List[Button]) -> List[Dict[str, Any]]:
        """
        Format the buttons to be sent to the client.
        """
        return [
            {
                "id": button.id,
                "custom_id": button.custom_id,
                "style": button.style,
                "label": button.label,
                "clicked": button.clicked,
                "remove_after_click": button.remove_after_click,
            }
            for button in buttons
        ]

    async def _format_user(self, user: Optional[User]) -> Dict[str, Any]:
        """
        Format the user to be sent to the client.
        """
        if not user:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "platform_ids": {
                identifier.platform: identifier.platform_id for identifier in await user.platform_ids.all()
            },
        }

    async def _format_channel(self, channel: Optional[Channel]) -> Dict[str, Any]:
        """
        Format the channel to be sent to the client.
        """
        if not channel:
            return None
        return {
            "id": channel.id,
            "name": channel.name,
            "platform_ids": {
                identifier.platform: identifier.platform_id for identifier in await channel.platform_ids.all()
            },
        }

    async def _format_guild(self, guild: Optional[Guild]) -> Dict[str, Any]:
        """
        Format the guild to be sent to the client.
        """
        if not guild:
            return None
        return {
            "id": guild.id,
            "name": guild.name,
            "platform_ids": {
                identifier.platform: identifier.platform_id for identifier in await guild.platform_ids.all()
            },
        }

    async def send_message(
        self,
        message: str,
        user: Optional[User],
        channel: Optional[Channel],
        buttons: Optional[List["ActionButton"]] = None,
        delete_after: Optional[int] = None,
    ):
        """
        Send a formatted message to the client by using `format_message`.
        """
        bot_message = await BotMessage.create(receiver=user, channel=channel, content=message)
        button_objects = [
            await Button.create(
                bot_message=bot_message,
                custom_id=button.custom_id,
                style=button.style,
                label=button.label,
                remove_after_click=button.remove_after_click,
            )
            for button in buttons or []
        ]
        data = {
            "receiver": await self._format_user(user),
            "channel": await self._format_channel(channel),
            "message": bot_message.content,
            "buttons": await self._format_buttons(button_objects),
            "delete_after": delete_after,
        }
        await self.send_json(
            {
                "action": ResponseTypes.MESSAGE,
                "content": data,
            }
        )

    async def send_image(
        self,
        image: File,
        user: Optional[User],
        channel: Optional[Channel],
        caption: Optional[str] = None,
        buttons: Optional[List["ActionButton"]] = None,
        delete_after: Optional[int] = None,
    ):
        """
        Send images to the client.
        """
        if buttons and not caption:
            raise ValueError("A caption must be provided when sending an image with buttons.")
        button_objects = [
            await Button.create(
                bot_message=None,
                custom_id=button.custom_id,
                style=button.style,
                label=button.label,
                remove_after_click=button.remove_after_click,
            )
            for button in buttons or []
        ]
        data = {
            "receiver": await self._format_user(user),
            "channel": await self._format_channel(channel),
            "image": await universal_image_storage.get_image_url(image.storage_file_object_key),
            "caption": caption,
            "buttons": await self._format_buttons(button_objects),
            "delete_after": delete_after,
        }
        await self.send_json(
            {
                "action": ResponseTypes.IMAGE,
                "content": data,
            }
        )

    async def send_static_image(
        self,
        image: str,
        user: Optional[User],
        channel: Optional[Channel],
        caption: Optional[str] = None,
        buttons: Optional[List["ActionButton"]] = None,
        action: ResponseTypes = ResponseTypes.STATIC_IMAGE,
        delete_after: Optional[int] = None,
    ):
        """
        Send static images to the client.
        """
        if action not in [ResponseTypes.STATIC_IMAGE, ResponseTypes.STATIC_GIF]:
            raise ValueError("action must be either `STATIC_IMAGE` or `STATIC_GIF`.")
        if action == ResponseTypes.STATIC_GIF and buttons:
            raise ValueError("action `STATIC_GIF` does not support buttons.")
        if action == ResponseTypes.STATIC_GIF and caption:
            raise ValueError("action `STATIC_GIF` does not support caption.")
        if buttons and not caption:
            raise ValueError("A caption must be provided when sending an image with buttons.")
        button_objects = [
            await Button.create(
                bot_message=None,
                custom_id=button.custom_id,
                style=button.style,
                label=button.label,
                remove_after_click=button.remove_after_click,
            )
            for button in buttons or []
        ]
        data = {
            "receiver": await self._format_user(user),
            "channel": await self._format_channel(channel),
            "image": image,
            "buttons": await self._format_buttons(button_objects),
            "delete_after": delete_after,
        }
        await self.send_json(
            {
                "action": action,
                "content": data,
            }
        )

    async def add_role(self, user: User, role: Role):
        await self.send_json(
            {
                "action": ResponseTypes.ADD_ROLE,
                "content": {
                    "role": {
                        "name": role.name,
                        "guild": await self._format_guild(role.guild),
                        "user": await self._format_user(user),
                    },
                },
            }
        )

    async def remove_role(self, user: User, role: Role):
        await self.send_json(
            {
                "action": ResponseTypes.REMOVE_ROLE,
                "content": {
                    "role": {
                        "name": role.name,
                        "guild": await self._format_guild(role.guild),
                        "user": await self._format_user(user),
                    },
                },
            }
        )

    async def set_typing(self, user: User, channel: Channel, action: ResponseTypes):
        if action not in [ResponseTypes.START_TYPING, ResponseTypes.STOP_TYPING]:
            raise ValueError("Action must be either `START_TYPING` or `STOP_TYPING`.")
        await self.send_json(
            {
                "action": action.value,
                "content": {
                    "receiver": await self._format_user(user),
                    "channel": await self._format_channel(channel),
                },
            }
        )

    @asynccontextmanager
    async def with_constant_typing(self, user: User, channel: Channel):
        """An asynchronous context manager for typing indicators or other tasks."""
        await self.set_typing(user, channel, ResponseTypes.START_TYPING)
        yield
        await self.set_typing(user, channel, ResponseTypes.STOP_TYPING)

    @abstractmethod
    async def send_json(self, data: Dict[str, Any]):
        """
        Send an action for the client.
        """
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

    async def stop_process(self, code: int = 1000, reason: Optional[str] = None):
        await self.interface.close(code, reason)

    async def send_json(self, data: Dict[str, Any]):
        await self.interface.send_json(data)


class APIInterface(BaseInterface):
    def __init__(self):
        self.messages = []

    async def send_json(self, data: Dict[str, Any]):
        self.messages.append(data)

    async def stop_process(self, *args, **kwargs):
        return self.messages
