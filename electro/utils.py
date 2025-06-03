from io import BytesIO
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException
from PIL import Image
from tortoise.queryset import QuerySet

from .models import BaseModel, File, Message, User
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
    files = [
        {
            "url": await universal_file_storage.get_file_url(file.storage_file_object_key),
            "height": file.height,
            "width": file.width,
            "content_type": file.content_type,
        }
        for file in message.files
    ]
    return {
        "id": message.id,
        "is_bot_message": message.is_bot_message,
        "date_added": message.date_added.timestamp(),
        "message": message.content,
        "files": files + (message.static_files or []),
        "buttons": buttons,
    }


async def limit_offset_paginate_response(
    data: QuerySet[BaseModel], formatter: Callable, limit: int, offset: int, url: str
) -> Dict[str, Any]:
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


async def limit_from_id_paginate_response(
    data: QuerySet[BaseModel], formatter: Callable, limit: int, from_id: Optional[int], url: str
) -> Dict[str, Any]:
    """
    Paginate the response data based on the latest ID.
    """
    if from_id is not None:
        latest_item = await data.get_or_none(id=from_id)
        if not latest_item:
            raise HTTPException(status_code=400, detail=f"Item with ID {from_id} not found.")
        data_from_id = data.filter(date_added__lt=latest_item.date_added)
    else:
        data_from_id = data
    fetched_data_from_id = await data_from_id.limit(limit + 1).all()
    if len(fetched_data_from_id) == limit + 1:
        next_from_id = fetched_data_from_id[limit - 1]
        next_page = f"{url}?limit={limit}&from_id={next_from_id.id}"
    else:
        next_page = None

    paginated_data = await data_from_id.limit(limit).all()
    formatted_data = [await formatter(message) for message in paginated_data]
    return {
        "from_id": from_id,
        "limit": limit,
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
