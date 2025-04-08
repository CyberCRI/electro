import contextvars
import pathlib
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import WebSocket

from .enums import ResponseTypes
from .models import BotMessage, Button, Channel, File, Guild, Role, User
from .settings import settings
from .toolkit.images_storage.universal_image_storage import universal_image_storage

if TYPE_CHECKING:
    from .contrib.buttons import BaseButton


class BaseInterface(ABC):
    """
    Interface class for the Electro framework.
    """

    async def _create_and_format_buttons(
        self, buttons: Optional[List["BaseButton"]] = None, bot_message: Optional[BotMessage] = None
    ) -> List[Button]:
        """
        Format the buttons to be sent to the client.
        """
        response = []
        for button in buttons or []:
            button_object = await Button.create(
                bot_message=bot_message,
                custom_id=button.custom_id,
                style=button.style,
                label=button.label,
                remove_after_click=button.remove_after_click,
                extra_data=getattr(button, "extra_data", {}),
            )
            response.append(
                {
                    "id": button_object.id,
                    "custom_id": button_object.custom_id,
                    "style": button_object.style,
                    "label": button_object.label,
                    "clicked": button_object.clicked,
                    "remove_after_click": button_object.remove_after_click,
                }
            )
        return response

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
        buttons: Optional[List["BaseButton"]] = None,
        delete_after: Optional[int] = None,
    ):
        """
        Send a formatted message to the client by using `format_message`.
        """
        bot_message = await BotMessage.create(receiver=user, channel=channel, content=message)
        data = {
            "user": await self._format_user(user),
            "channel": await self._format_channel(channel),
            "message": bot_message.content,
            "buttons": await self._create_and_format_buttons(buttons, bot_message),
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
        image: File | BytesIO | str | pathlib.Path,
        user: Optional[User],
        channel: Optional[Channel],
        caption: Optional[str] = None,
        buttons: Optional[List["BaseButton"]] = None,
        delete_after: Optional[int] = None,
    ):
        """
        Send images to the client.
        """
        if buttons and not caption:
            raise ValueError("A caption must be provided when sending an image with buttons.")
        if isinstance(image, File):
            image_url = await universal_image_storage.get_image_url(image.storage_file_object_key)
        elif isinstance(image, BytesIO):
            object_key = await universal_image_storage.upload_image(image)
            await File.create(
                owner=user,
                storage_service=settings.STORAGE_SERVICE_ID,
                storage_file_object_key=object_key,
            )
            image_url = await universal_image_storage.get_image_url(object_key)
        else:
            image_url = str(image)
        if image_url.startswith(settings.APP_ROOT):
            image_url = settings.SERVER_URL + image_url[len(settings.APP_ROOT) :]
        if str(image_url).endswith(".gif") and (buttons or caption):
            raise ValueError("GIFs do not support buttons or captions.")

        data = {
            "user": await self._format_user(user),
            "channel": await self._format_channel(channel),
            "image": image_url,
            "caption": caption,
            "buttons": await self._create_and_format_buttons(buttons),
            "delete_after": delete_after,
        }
        await self.send_json(
            {
                "action": ResponseTypes.IMAGE,
                "content": data,
            }
        )

    async def add_role(self, user: User, role: Role):
        await self.send_json(
            {
                "action": ResponseTypes.ADD_ROLE,
                "content": {
                    "role": role.name,
                    "guild": await self._format_guild(role.guild),
                    "user": await self._format_user(user),
                },
            }
        )

    async def remove_role(self, user: User, role: Role):
        await self.send_json(
            {
                "action": ResponseTypes.REMOVE_ROLE,
                "content": {
                    "role": role.name,
                    "guild": await self._format_guild(role.guild),
                    "user": await self._format_user(user),
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
                    "user": await self._format_user(user),
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
        self.messages = contextvars.ContextVar("messages")
        self.messages.set([])

    async def send_json(self, data: Dict[str, str]):
        self.messages.get().append(data)

    async def stop_process(self, *args, **kwargs):
        return self.messages.get()
