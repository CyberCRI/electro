from typing import Any, Callable, Dict

from tortoise.queryset import QuerySet

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
            image_url = await universal_image_storage.get_file_url(image.storage_file_object_key)
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


async def paginate_response(data: QuerySet, formatter: Callable, limit: int, offset: int, url: str) -> Dict[str, Any]:
    """
    Paginate the response data.
    """
    total_count = await data.count()
    paginated_data = await data.offset(offset).limit(limit).all()
    formatted_data = [await formatter(message) for message in paginated_data]
    previous_page = f"{url}?limit={limit}&offset={max(0, offset - limit)}" if offset > 0 else None
    next_page = f"{url}?limit={limit}&offset={offset + limit}" if offset + limit < total_count else None
    total_pages = (total_count + limit - 1) // limit
    current_page = offset // limit + 1
    return {
        "count": total_count,
        "offset": offset,
        "limit": limit,
        "pages": total_pages,
        "page": current_page,
        "previous": previous_page,
        "next": next_page,
        "data": formatted_data,
    }
