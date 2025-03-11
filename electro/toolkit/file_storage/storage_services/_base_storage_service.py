"""Base storage service for file handling."""

from abc import ABC, abstractmethod
from io import BytesIO
from typing import BinaryIO, Dict, Any, Optional
from datetime import datetime

class BaseFileStorageService(ABC):
    """Base class for file storage services."""

    @abstractmethod
    async def upload_file(
        self, 
        file: BinaryIO, 
        filename: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Uploads a file to the storage and returns the object key.

        Args:
            file: File-like object to upload
            filename: Original filename
            content_type: MIME type of the file
            metadata: Additional metadata to store with the file

        Returns:
            str: Object key of the uploaded file
        """
        raise NotImplementedError

    @abstractmethod
    async def download_file(self, object_key: str) -> BytesIO:
        """Downloads a file from storage and returns a BytesIO object.

        Args:
            object_key: Object key of the file to download

        Returns:
            BytesIO: File contents
        """
        raise NotImplementedError

    @abstractmethod
    async def get_file_metadata(self, object_key: str) -> Dict[str, Any]:
        """Gets metadata for a file.

        Args:
            object_key: Object key of the file

        Returns:
            Dict[str, Any]: File metadata including size, content type, etc.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, object_key: str) -> None:
        """Deletes a file from storage.

        Args:
            object_key: Object key of the file to delete
        """
        raise NotImplementedError

    @abstractmethod
    async def check_file_exists(self, object_key: str) -> bool:
        """Checks if a file exists in storage.

        Args:
            object_key: Object key of the file

        Returns:
            bool: True if file exists, False otherwise
        """
        raise NotImplementedError
