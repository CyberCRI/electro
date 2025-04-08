from io import BytesIO
from typing import Type

from ...settings import settings
from .storage_services import AzureBlobStorageService, BaseStorageService, S3Service
from .storages_enums import StoragesIDs


class UniversalImageStorage:
    """
    The UniversalImageStorage class is responsible for uploading and downloading images to and from a storage service.

    It can be used with any storage service that implements the BaseStorageService class.
    """

    def __init__(self, storage_service: BaseStorageService):
        """Initialize the UniversalImageStorage class."""
        self.storage_service = storage_service

    async def upload_image(self, image_io: BytesIO) -> str:
        """Upload an image to the storage service."""
        return await self.storage_service.upload_image(image_io)

    async def download_image(self, object_key: str) -> BytesIO:
        """Download an image from the storage service."""
        return await self.storage_service.download_image(object_key)

    async def get_image_url(self, object_key: str) -> str:
        """Get the URL of the image from the storage service."""
        return await self.storage_service.get_image_url(object_key)


STORAGES_IDS_TO_SERVICES = {
    StoragesIDs.S3: S3Service,
    StoragesIDs.AZURE_BLOB_STORAGE: AzureBlobStorageService,
}


def choose_storage_service(default: StoragesIDs = StoragesIDs.S3) -> BaseStorageService:
    """Choose the storage service to use based on the default value."""
    storage_id: StoragesIDs = StoragesIDs(settings.STORAGE_SERVICE_ID) if settings.STORAGE_SERVICE_ID else default

    storage_service_class: Type[BaseStorageService] = STORAGES_IDS_TO_SERVICES[storage_id]
    return storage_service_class()


universal_image_storage = UniversalImageStorage(storage_service=choose_storage_service())
