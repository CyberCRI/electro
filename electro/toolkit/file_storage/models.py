"""Database models for file storage."""

from tortoise import fields
from tortoise.models import Model
from datetime import datetime
from typing import Optional

class File(Model):
    """File metadata model."""
    
    id = fields.UUIDField(pk=True)
    filename = fields.CharField(max_length=255)
    object_key = fields.CharField(max_length=512, unique=True)
    size_bytes = fields.BigIntField()
    content_type = fields.CharField(max_length=255, null=True)
    storage_service = fields.CharField(max_length=50)  # e.g., "local", "s3", "azure"
    metadata = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_add_now=True)
    updated_at = fields.DatetimeField(auto_add=True)

    class Meta:
        """Model metadata."""
        table = "files"

    def __str__(self) -> str:
        """String representation of the file."""
        return f"{self.filename} ({self.id})"

    async def get_download_url(self) -> str:
        """Get the download URL for this file."""
        # TODO: Implement URL generation based on storage service
        return f"/api/files/download/{self.id}"

    @property
    def size_formatted(self) -> str:
        """Get human-readable file size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024
        return f"{self.size_bytes:.1f} TB"
