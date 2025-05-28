"""The `BaseStorageService` is an abstract class that defines the interface for a storage service."""

from abc import ABC, abstractmethod
from io import BytesIO


class BaseStorageService(ABC):
    """Base class for storage services."""

    @abstractmethod
    async def upload_file(self, file_io: BytesIO, content_type: str) -> str:
        """Uploads an file to the storage and returns the object key.

        :param file_io: BytesIO object of the file to upload
        :return: object key of the uploaded file

        """
        raise NotImplementedError

    @abstractmethod
    async def download_file(self, object_key: str) -> BytesIO:
        """Downloads an file from the storage and returns a BytesIO object.

        :param object_key: object key of the file to download
        :return: BytesIO object of the downloaded file

        """
        raise NotImplementedError

    @abstractmethod
    async def get_file_url(self, object_key: str) -> str:
        """Returns the URL of the file.

        :param object_key: object key of the file
        :return: URL of the file

        """
        raise NotImplementedError
