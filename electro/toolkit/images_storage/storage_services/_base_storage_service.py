"""The `BaseStorageService` is an abstract class that defines the interface for a storage service."""

from abc import ABC, abstractmethod
from io import BytesIO


class BaseStorageService(ABC):
    """Base class for storage services."""

    @abstractmethod
    async def upload_image(self, image_io: BytesIO) -> str:
        """Uploads an image to the storage and returns the object key.

        :param image_io: BytesIO object of the image to upload
        :return: object key of the uploaded image

        """
        raise NotImplementedError

    @abstractmethod
    async def download_image(self, object_key: str) -> BytesIO:
        """Downloads an image from the storage and returns a BytesIO object.

        :param object_key: object key of the image to download
        :return: BytesIO object of the downloaded image

        """
        raise NotImplementedError
