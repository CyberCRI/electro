"""Local file storage implementation."""

import os
import shutil
from datetime import datetime
from io import BytesIO
from typing import BinaryIO, Dict, Any, Optional
from pathlib import Path

from ._base_storage_service import BaseFileStorageService
from ...settings import Settings

class LocalFileStorage(BaseFileStorageService):
    """Local file storage service implementation."""

    def __init__(self, base_path: Optional[str] = None):
        """Initialize local storage service.
        
        Args:
            base_path: Base path for file storage. If not provided, uses settings.LOCAL_STORAGE_PATH
        """
        settings = Settings.get_current()
        self.base_path = Path(base_path or settings.LOCAL_STORAGE_PATH).absolute()
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Upload a file to local storage.
        
        Args:
            file: File-like object to upload
            filename: Original filename
            content_type: MIME type of the file
            metadata: Additional metadata to store with the file
            
        Returns:
            str: Object key (relative path) of the uploaded file
        """
        # Create a unique path for the file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        object_key = f"{timestamp}_{safe_filename}"
        file_path = self.base_path / object_key

        # Save the file
        with open(file_path, "wb") as dest_file:
            shutil.copyfileobj(file, dest_file)

        # Save metadata if provided
        if metadata:
            metadata_path = file_path.with_suffix(file_path.suffix + ".meta")
            with open(metadata_path, "w") as meta_file:
                import json
                json.dump({
                    "content_type": content_type,
                    "original_filename": filename,
                    "created_at": timestamp,
                    **metadata
                }, meta_file)

        return object_key

    async def download_file(self, object_key: str) -> BytesIO:
        """Download a file from local storage.
        
        Args:
            object_key: Object key (relative path) of the file
            
        Returns:
            BytesIO: File contents
        """
        file_path = self.base_path / object_key
        if not file_path.exists():
            raise FileNotFoundError(f"File {object_key} not found")

        buffer = BytesIO()
        with open(file_path, "rb") as src_file:
            shutil.copyfileobj(src_file, buffer)
        
        buffer.seek(0)
        return buffer

    async def get_file_metadata(self, object_key: str) -> Dict[str, Any]:
        """Get metadata for a file.
        
        Args:
            object_key: Object key of the file
            
        Returns:
            Dict[str, Any]: File metadata
        """
        file_path = self.base_path / object_key
        if not file_path.exists():
            raise FileNotFoundError(f"File {object_key} not found")

        stat = file_path.stat()
        metadata = {
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime),
            "modified_at": datetime.fromtimestamp(stat.st_mtime),
        }

        # Try to load additional metadata if exists
        meta_path = file_path.with_suffix(file_path.suffix + ".meta")
        if meta_path.exists():
            with open(meta_path, "r") as meta_file:
                import json
                metadata.update(json.load(meta_file))

        return metadata

    async def delete_file(self, object_key: str) -> None:
        """Delete a file from local storage.
        
        Args:
            object_key: Object key of the file to delete
        """
        file_path = self.base_path / object_key
        if not file_path.exists():
            raise FileNotFoundError(f"File {object_key} not found")

        # Delete the file and its metadata
        file_path.unlink()
        
        meta_path = file_path.with_suffix(file_path.suffix + ".meta")
        if meta_path.exists():
            meta_path.unlink()

    async def check_file_exists(self, object_key: str) -> bool:
        """Check if a file exists in local storage.
        
        Args:
            object_key: Object key of the file
            
        Returns:
            bool: True if file exists, False otherwise
        """
        file_path = self.base_path / object_key
        return file_path.exists()
