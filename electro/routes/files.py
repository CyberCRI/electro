"""API routes for file handling."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File as FastAPIFile, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..toolkit.file_storage.models import File
from ..toolkit.file_storage.storage_services import LocalFileStorage
from ..settings import Settings

router = APIRouter(prefix="/api/files", tags=["files"])

# Response models
class FileMetadata(BaseModel):
    """File metadata response model."""
    id: str
    filename: str
    size_bytes: int
    content_type: Optional[str]
    download_url: str
    created_at: str

class FileList(BaseModel):
    """File list response model."""
    total: int
    page: int
    page_size: int
    files: List[FileMetadata]

# Dependencies
async def get_storage_service():
    """Get the configured storage service."""
    settings = Settings.get_current()
    if settings.FILE_STORAGE_SERVICE == "local":
        return LocalFileStorage()
    # TODO: Add other storage services
    raise ValueError(f"Unsupported storage service: {settings.FILE_STORAGE_SERVICE}")

@router.post("/upload", response_model=FileMetadata)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    storage_service: LocalFileStorage = Depends(get_storage_service)
):
    """Upload a file."""
    try:
        settings = Settings.get_current()
        
        # Validate file size
        file_size = 0
        chunk_size = 8192  # 8KB chunks
        chunks = []
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            chunks.append(chunk)
            
            if file_size > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE} bytes"
                )

        # Reset file pointer
        await file.seek(0)
        
        # Upload file to storage
        object_key = await storage_service.upload_file(
            file.file,
            file.filename,
            content_type=file.content_type
        )
        
        # Save metadata to database
        db_file = await File.create(
            id=uuid.uuid4(),
            filename=file.filename,
            object_key=object_key,
            size_bytes=file_size,
            content_type=file.content_type,
            storage_service=settings.FILE_STORAGE_SERVICE
        )
        
        return FileMetadata(
            id=str(db_file.id),
            filename=db_file.filename,
            size_bytes=db_file.size_bytes,
            content_type=db_file.content_type,
            download_url=await db_file.get_download_url(),
            created_at=db_file.created_at.isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    storage_service: LocalFileStorage = Depends(get_storage_service)
):
    """Download a file."""
    file = await File.get_or_none(id=file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file_data = await storage_service.download_file(file.object_key)
        
        return StreamingResponse(
            file_data,
            media_type=file.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file.filename}"',
                "Content-Length": str(file.size_bytes)
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{file_id}", response_model=FileMetadata)
async def get_file_metadata(file_id: str):
    """Get file metadata."""
    file = await File.get_or_none(id=file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileMetadata(
        id=str(file.id),
        filename=file.filename,
        size_bytes=file.size_bytes,
        content_type=file.content_type,
        download_url=await file.get_download_url(),
        created_at=file.created_at.isoformat()
    )

@router.get("", response_model=FileList)
async def list_files(
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc"
):
    """List files with pagination."""
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Page size must be between 1 and 100")
    
    # Validate sort parameters
    valid_sort_fields = {"created_at", "filename", "size_bytes"}
    if sort_by not in valid_sort_fields:
        raise HTTPException(status_code=400, detail=f"Sort field must be one of: {valid_sort_fields}")
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Sort order must be 'asc' or 'desc'")
    
    total = await File.all().count()
    files = await File.all().order_by(
        f"{'-' if sort_order == 'desc' else ''}{sort_by}"
    ).offset((page - 1) * page_size).limit(page_size)
    
    return FileList(
        total=total,
        page=page,
        page_size=page_size,
        files=[
            FileMetadata(
                id=str(file.id),
                filename=file.filename,
                size_bytes=file.size_bytes,
                content_type=file.content_type,
                download_url=await file.get_download_url(),
                created_at=file.created_at.isoformat()
            )
            for file in files
        ]
    )
