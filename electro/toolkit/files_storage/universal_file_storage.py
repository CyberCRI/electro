from io import BytesIO
from typing import Type

from ...settings import settings
from .storage_services import AzureBlobStorageService, BaseStorageService, S3Service
from .storages_enums import StoragesIDs


class UniversalFileStorage:
    """
    The UniversalFileStorage class is responsible for uploading and downloading files to and from a storage service.

    It can be used with any storage service that implements the BaseStorageService class.
    """

    def __init__(self, storage_service: BaseStorageService):
        """Initialize the UniversalFileStorage class."""
        self.storage_service = storage_service

    async def upload_file(self, file_io: BytesIO, content_type: str, *, make_public: bool = False) -> str:
        """Upload an file to the storage service."""
        return await self.storage_service.upload_file(file_io, content_type, make_public=make_public)

    async def download_file(self, object_key: str) -> BytesIO:
        """Download an file from the storage service."""
        return await self.storage_service.download_file(object_key)

    async def get_file_url(self, object_key: str) -> str:
        """Get the URL of the file from the storage service."""
        return await self.storage_service.get_file_url(object_key)


STORAGES_IDS_TO_SERVICES = {
    StoragesIDs.S3: S3Service,
    StoragesIDs.AZURE_BLOB_STORAGE: AzureBlobStorageService,
}


def choose_storage_service(default: StoragesIDs = StoragesIDs.S3) -> BaseStorageService:
    """Choose the storage service to use based on the default value."""
    storage_id: StoragesIDs = StoragesIDs(settings.STORAGE_SERVICE_ID) if settings.STORAGE_SERVICE_ID else default

    storage_service_class: Type[BaseStorageService] = STORAGES_IDS_TO_SERVICES[storage_id]
    return storage_service_class()


universal_file_storage = UniversalFileStorage(storage_service=choose_storage_service())
