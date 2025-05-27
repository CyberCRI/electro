"""The S3Service class is responsible for uploading and downloading images to and from an S3 bucket."""

from io import BytesIO
from uuid import uuid4

from aioboto3 import Session
from botocore.exceptions import ClientError

from ....settings import settings
from ....toolkit.images_storage.storage_services._base_storage_service import BaseStorageService
from ....toolkit.loguru_logging import logger


class S3Service(BaseStorageService):
    """The S3Service class is responsible for uploading and downloading images to and from an S3 bucket."""

    # TODO: [13.06.2024 by Mykola] Allow the bucket_name to be passed as an argument to the __init__ method.
    # def __init__(self, bucket_name: str | None = None):
    def __init__(self, bucket_name: str | None = None):
        """Initialize the S3Service class."""
        self.session = Session(
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION_NAME,
        )
        self.bucket_name = bucket_name or settings.S3_IMAGES_BUCKET_NAME

    async def ensure_bucket_exists(self):
        """Ensure that the S3 bucket exists."""
        async with self.session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL) as s3:
            try:
                await s3.head_bucket(Bucket=self.bucket_name)
                logger.info(f"Bucket {self.bucket_name} exists.")
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "404":
                    logger.warning(f"Bucket {self.bucket_name} does not exist. Creating it now.")
                    await s3.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Bucket {self.bucket_name} created successfully.")
                else:
                    logger.error(f"Error checking bucket {self.bucket_name}: {e}")
                    raise

    async def _upload_file(self, file_io: BytesIO, object_key: str, extra_args: dict | None = None):
        """Upload a file to the S3 bucket."""
        await self.ensure_bucket_exists()
        async with self.session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL) as s3:
            await s3.upload_fileobj(file_io, self.bucket_name, object_key, ExtraArgs=extra_args)
            logger.info(f"Image uploaded successfully: {object_key}")

    async def _download_file(self, object_key: str, destination: str | BytesIO | None = None) -> str | BytesIO:
        """Download a file from the S3 bucket."""
        await self.ensure_bucket_exists()
        if not destination:
            destination = f"/tmp/{object_key}"

        async with self.session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL) as s3:
            if isinstance(destination, str):
                await s3.download_file(self.bucket_name, object_key, destination)
            elif isinstance(destination, BytesIO):
                await s3.download_fileobj(self.bucket_name, object_key, destination)
            logger.info(f"Image downloaded successfully: {object_key}")

            return destination

    async def upload_file(self, image_io: BytesIO) -> str:
        """Uploads an image to the S3 bucket and returns the object key.

        :param image_io: BytesIO object of the image to upload
        :return: object key of the uploaded image

        """
        object_key = str(uuid4())
        try:
            # TODO: [2024-10-05 by Mykola] IT'S NOT ALWAYS JPEG
            await self._upload_file(image_io, object_key, extra_args={"ContentType": "image/jpeg"})
            logger.info(f"Image uploaded successfully: {object_key}")
            return object_key
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            raise

    async def download_file(self, object_key: str) -> BytesIO:
        """Downloads an image from the S3 bucket and returns a BytesIO object.

        :param object_key: object key of the image to download
        :return: BytesIO object of the downloaded image

        """
        image_io = BytesIO()
        try:
            await self._download_file(object_key, image_io)
            logger.info(f"Image downloaded successfully: {object_key}")
            return image_io
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            raise

    async def get_file_url(self, object_key: str) -> str:
        """Returns the URL of the image.

        :param object_key: object key of the image
        :return: URL of the image

        """
        async with self.session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL):
            try:
                url = f"{settings.S3_ENDPOINT_URL}/{self.bucket_name}/{object_key}"
                logger.info(f"Image URL: {url}")
                return url
            except Exception as e:
                logger.error(f"Failed to get image URL: {e}")
                raise
