"""Azure Blob Storage Service Module."""

import os
from io import BytesIO

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from ....settings import settings
from ...images_storage.storage_services._base_storage_service import BaseStorageService


class AzureBlobStorageService(BaseStorageService):
    """Azure Blob Storage Service Class."""

    def __init__(self, container_name: str | None = None):
        """Initialize the AzureBlobStorageService class."""
        self.container_name = container_name or settings.AZURE_CONTAINER_NAME

        self.__account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        self.__credential = DefaultAzureCredential(
            # No need to pass the `client_id`, `tenant_id`, and `client_secret` as they are read from the environment
        )

        self._blob_service_client = None

    @property
    async def blob_service_client(self) -> BlobServiceClient:
        """Get the Azure Blob Service Client."""
        return BlobServiceClient(
            account_url=self.__account_url,
            credential=self.__credential,  # type: ignore
        )

    async def _ensure_container_exists(self):
        """Ensure that the container exists in the Azure Blob Storage."""
        async with await self.blob_service_client as client:
            container_client = client.get_container_client(self.container_name)
            try:
                await container_client.get_container_properties()
            except ResourceNotFoundError:
                await container_client.create_container()

    async def upload_image(self, image_io: BytesIO) -> str:
        """Upload an image to the Azure Blob Storage."""
        blob_name = f"image_{os.urandom(8).hex()}.png"
        async with await self.blob_service_client as client:
            await self._ensure_container_exists()
            container_client = client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.upload_blob(image_io, blob_type="BlockBlob")
        return blob_name

    async def download_image(self, object_key: str) -> BytesIO:
        """Download an image from the Azure Blob Storage."""
        async with await self.blob_service_client as client:
            container_client = client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(object_key)
            try:
                image_data = await blob_client.download_blob()
            except ResourceNotFoundError:
                raise FileNotFoundError(f"Image with key '{object_key}' not found in the Azure Blob Storage.")
            return BytesIO(await image_data.readall())

    async def get_image_url(self, object_key: str) -> str:
        """Get the URL of an image in the Azure Blob Storage."""
        async with await self.blob_service_client as client:
            container_client = client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(object_key)
            try:
                url = blob_client.url
            except ResourceNotFoundError:
                raise FileNotFoundError(f"Image with key '{object_key}' not found in the Azure Blob Storage.")
            return url
