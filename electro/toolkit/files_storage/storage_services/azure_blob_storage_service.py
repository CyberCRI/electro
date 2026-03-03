"""Azure Blob Storage Service Module."""

import datetime
import os
from io import BytesIO

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, ContentSettings, generate_blob_sas
from azure.storage.blob.aio import BlobClient, BlobServiceClient

from ....settings import settings
from ...files_storage.storage_services._base_storage_service import BaseStorageService


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

    async def upload_file(self, file_io: BytesIO, content_type: str, *, make_public: bool = False) -> str:
        """Upload a file to the Azure Blob Storage.

        Note: make_public is accepted for API consistency but Azure blob public access
        is controlled at the container level. Use SAS tokens via get_file_url() for access.
        """
        _ = make_public  # Azure public access is container-level, not per-blob
        blob_name = f"file_{os.urandom(8).hex()}.png"
        async with await self.blob_service_client as client:
            await self._ensure_container_exists()
            container_client = client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.upload_blob(
                file_io, blob_type="BlockBlob", content_settings=ContentSettings(content_type=content_type)
            )
        return blob_name

    async def download_file(self, object_key: str) -> BytesIO:
        """Download an file from the Azure Blob Storage."""
        async with await self.blob_service_client as client:
            container_client = client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(object_key)
            try:
                file_data = await blob_client.download_blob()
            except ResourceNotFoundError as e:
                raise FileNotFoundError(f"File with key '{object_key}' not found in the Azure Blob Storage.") from e
            return BytesIO(await file_data.readall())

    async def _create_file_access_token(self, blob_client: BlobClient) -> str:
        start_time = datetime.datetime.now(datetime.timezone.utc)
        expiry_time = start_time + datetime.timedelta(days=1)
        return generate_blob_sas(
            account_name=blob_client.account_name,
            container_name=blob_client.container_name,
            blob_name=blob_client.blob_name,
            account_key=settings.AZURE_ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=expiry_time,
            start=start_time,
        )

    async def get_file_url(self, object_key: str) -> str:
        """Get the URL of an file in the Azure Blob Storage."""
        async with await self.blob_service_client as client:
            container_client = client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(object_key)
            token = await self._create_file_access_token(blob_client)
            return f"{blob_client.url}?{token}"
