from typing import Any, Dict

from .models import Message
from .toolkit.images_storage.universal_image_storage import universal_image_storage


async def format_historical_message(message: Message) -> Dict[str, Any]:
    await message.fetch_related("buttons", "files")
    buttons = [
        {
            "id": button.id,
            "custom_id": button.custom_id,
            "style": button.style,
            "label": button.label,
            "clicked": button.clicked,
            "remove_after_click": button.remove_after_click,
        }
        for button in message.buttons
    ]
    if message.type == Message.MessageTypes.IMAGE:
        if len(message.files) > 0:
            image = message.files[0]
            image_url = await universal_image_storage.get_image_url(image.storage_file_object_key)
        else:
            image_url = message.content
        return {
            "id": message.id,
            "type": message.type,
            "is_bot_message": message.is_bot_message,
            "image": image_url,
            "caption": message.caption,
            "buttons": buttons,
        }
    if message.type == Message.MessageTypes.TEXT:
        return {
            "id": message.id,
            "type": message.type,
            "is_bot_message": message.is_bot_message,
            "message": message.content,
            "buttons": buttons,
        }
    return {}
