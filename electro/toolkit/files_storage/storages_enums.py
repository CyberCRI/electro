"""Enums for storage services."""

from enum import Enum


class StoragesIDs(str, Enum):
    """Enum for storage services."""

    S3 = "S3"
    AZURE_BLOB_STORAGE = "AzureBlobStorage"
