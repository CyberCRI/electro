import contextvars
import pathlib
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union

from fastapi import WebSocket

from .enums import ResponseTypes, SupportedPlatforms
from .flow_connector import FlowConnectorEvents
from .flow_manager import global_flow_manager
from .models import Button, Channel, File, Guild, Message, Role, User
from .schemas import ButtonClick, ReceivedMessage
from .settings import settings
from .toolkit.images_storage.universal_image_storage import universal_image_storage

if TYPE_CHECKING:
    from .contrib.buttons import BaseButton


class BaseInterface(ABC):
    """
    Interface class for the Electro framework. This class is used to receive messages and events from the client and
    send back tasks to be executed.

    To use it, you need to inherit from this class and implement the `send_json` method. This method is called
    whenever a task is sent to the client. You can also override the `handle_incoming_action` method to handle
    more incoming actions from the client.
    """

    async def _create_and_format_buttons(
        self, buttons: Optional[List["BaseButton"]] = None, message: Optional[Message] = None
    ) -> List[Button]:
        """Format the buttons to be sent to the client."""
        response = []
        for button in buttons or []:
            button_object = await Button.create(
                message=message,
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
        """Format the user to be sent to the client."""
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
        """Format the channel to be sent to the client."""
        if not channel:
            return None
        return {
            "id": channel.id,
            "name": channel.name,
            "type": channel.type,
            "platform_ids": {
                identifier.platform: identifier.platform_id for identifier in await channel.platform_ids.all()
            },
        }

    async def _format_guild(self, guild: Optional[Guild]) -> Dict[str, Any]:
        """Format the guild to be sent to the client."""
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
        delete_after: Optional[Union[int, str]] = None,
    ):
        """
        Send a formatted message to the client.

        Arguments:
            message: The message to be sent.
            user: The user who will receive the message.
            channel: The channel the message is being sent to.
            buttons: A list of buttons to be included with the message.
            delete_after: The time in seconds after which the message should be deleted.
                - if None, the message will not be deleted.
                - if "next", the message will be deleted after the next message is sent.
                - if an integer, the message will be deleted after that many seconds.
        """
        message_chunks = message.split(settings.MESSAGE_BREAK)
        user_data = await self._format_user(user)
        channel_data = await self._format_channel(channel)
        for i, message_chunk in enumerate(message_chunks):
            message = await Message.create(
                is_temporary=delete_after is not None,
                is_bot_message=True,
                type=Message.MessageTypes.TEXT,
                user=user,
                channel=channel,
                content=message_chunk,
            )
            if i == len(message_chunks) - 1:
                buttons = await self._create_and_format_buttons(buttons, message)
            else:
                buttons = []
            data = {
                "user": user_data,
                "channel": channel_data,
                "message": message_chunk,
                "buttons": buttons,
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
        Send images to the client as a link:

        If the image is a File, the link to the blob storage location will be sent.
        If the image is a BytesIO object, it will be uploaded to blob storage and the link will be sent.
        If the image is a string, it will be sent as is so make sure it is a valid URL.
        If the image is a pathlib.Path object, it will be sent as a link to the static file endpoint.

        Arguments:
            image: The image to be sent.
            user: The user who will receive the image.
            channel: The channel the image is being sent to.
            caption: The caption to be included with the image.
            buttons: A list of buttons to be included with the image.
            delete_after: The time in seconds after which the image should be deleted.
                - if None, the image will not be deleted.
                - if "next", the image will be deleted after the next message is sent.
                - if an integer, the image will be deleted after that many seconds.

        """
        if buttons and not caption:
            raise ValueError("A caption must be provided when sending an image with buttons.")
        if isinstance(image, File):
            image_url = await universal_image_storage.get_file_url(image.storage_file_object_key)
        elif isinstance(image, BytesIO):
            object_key = await universal_image_storage.upload_file(image)
            image = await File.create(
                owner=user,
                storage_service=settings.STORAGE_SERVICE_ID,
                storage_file_object_key=object_key,
            )
            image_url = await universal_image_storage.get_file_url(object_key)
        else:
            image_url = str(image)
        if image_url.startswith(settings.APP_ROOT):
            image_url = settings.SERVER_URL + image_url[len(settings.APP_ROOT) :]
        if str(image_url).endswith(".gif") and (buttons or caption):
            raise ValueError("GIFs do not support buttons or captions.")

        message = await Message.create(
            is_temporary=delete_after is not None,
            is_bot_message=True,
            type=Message.MessageTypes.IMAGE,
            user=user,
            channel=channel,
            content=image_url,
            caption=caption,
        )
        if isinstance(image, File):
            await message.files.add(image)
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
        """
        Assign a role to a user.

        Arguments:
            user: The user to whom the role will be assigned.
            role: The role to be assigned to the user.
        """
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
        """
        Remove a role from a user.

        Arguments:
            user: The user from whom the role will be removed.
            role: The role to be removed from the user.
        """
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
        """
        Set the typing indicator for a user or a channel.

        Arguments:
            user: The user for whom the typing indicator will be set.
            channel: The channel in which the typing indicator will be set.
            action: The action to be performed (either "start_typing" or "stop_typing").
        """
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

    async def stop_process(self):
        """
        Stop the process for the client.

        This is used to stop the process for the client and close the connection.
        """
        await self.send_json(
            {
                "action": ResponseTypes.STOP_PROCESS,
                "content": {},
            }
        )

    @asynccontextmanager
    async def with_constant_typing(self, user: User, channel: Channel):
        """An asynchronous context manager for typing indicators or other tasks."""
        await self.set_typing(user, channel, ResponseTypes.START_TYPING)
        yield
        await self.set_typing(user, channel, ResponseTypes.STOP_TYPING)

    async def handle_incoming_action(
        self, user: User, platform: SupportedPlatforms, data: Dict[str, Any]
    ) -> Tuple[Dict[str, str], int]:
        """
        Handle incoming actions from the client. The action data is validated and processed.

        Arguments:
            platform: The platform from which the action was received ().
            data: The data received from the client.
        """
        try:
            action = data.get("action")
            content = data.get("content")
            if action == FlowConnectorEvents.MESSAGE:
                content = ReceivedMessage.model_validate(content)
                await global_flow_manager.on_message(user, platform, content, self)
            if action == FlowConnectorEvents.BUTTON_CLICK:
                content = ButtonClick.model_validate(content)
                await global_flow_manager.on_button_click(user, platform, content, self)
            if action == FlowConnectorEvents.MEMBER_JOIN:
                pass
            if action == FlowConnectorEvents.MEMBER_UPDATE:
                pass
        except Exception as exception:  # pylint: disable=W0718
            await self.send_json(
                {
                    "action": ResponseTypes.ERROR,
                    "content": {
                        "error": str(exception),
                    },
                }
            )

    @abstractmethod
    async def send_json(self, data: Dict[str, Any]):
        """Send an task for the client to process."""
        raise NotImplementedError


class WebSocketInterface(BaseInterface):
    """WebSocket Interface for the Electro framework."""

    def __init__(self):
        self.interface: WebSocket | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.interface = websocket

    async def disconnect(self):
        await self.interface.close()
        self.interface = None

    async def stop_process(self, code: int = 1000, reason: Optional[str] = None):
        await super().stop_process()
        await self.interface.close(code, reason)

    async def send_json(self, data: Dict[str, Any]):
        await self.interface.send_json(data)


class APIInterface(BaseInterface):
    """API Interface for the Electro framework."""

    def __init__(self):
        self.messages = contextvars.ContextVar("messages")
        self.messages.set([])

    async def send_json(self, data: Dict[str, str]):
        self.messages.get().append(data)
