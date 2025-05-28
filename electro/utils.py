from io import BytesIO
from typing import Any, Callable, Dict

from PIL import Image
from tortoise.queryset import QuerySet

from .models import File, Message, User
from .settings import settings
from .toolkit.files_storage.universal_file_storage import universal_file_storage


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
            image_url = await universal_file_storage.get_file_url(image.storage_file_object_key)
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


async def create_and_upload_file(file: BytesIO, owner: User, content_type: str) -> File:
    if content_type.startswith("image/"):
        try:
            file.seek(0)
            with Image.open(file) as img:
                width, height = img.width, img.height
        except Exception:  # pylint: disable=W0718
            width, height = None, None
    else:
        width, height = None, None
    object_key = await universal_file_storage.upload_file(file, content_type=content_type)
    return await File.create(
        owner=owner,
        content_type=content_type,
        width=width,
        height=height,
        storage_service=settings.STORAGE_SERVICE_ID,
        storage_file_object_key=object_key,
    )
