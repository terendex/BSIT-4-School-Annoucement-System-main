"""Attachment storage.

Cloudinary in production (Render's disk is ephemeral), local MEDIA_ROOT in dev
when no Cloudinary credentials are configured.
"""
import logging
import os
import uuid

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def upload_attachment(uploaded_file, kind: str, safe_filename: str) -> dict:
    """Store the file and return the metadata the Attachment model needs."""
    if settings.CLOUDINARY_ENABLED:
        return _upload_to_cloudinary(uploaded_file, kind, safe_filename)
    return _upload_to_local(uploaded_file, kind, safe_filename)


def delete_attachment(attachment) -> None:
    """Best-effort remote/local delete. Never blocks the DB delete."""
    try:
        if attachment.storage_backend == "cloudinary" and attachment.public_id:
            import cloudinary.uploader

            cloudinary.uploader.destroy(
                attachment.public_id,
                resource_type=attachment.resource_type or "image",
                invalidate=True,
            )
        elif attachment.storage_backend == "local" and attachment.public_id:
            if default_storage.exists(attachment.public_id):
                default_storage.delete(attachment.public_id)
    except Exception:  # noqa: BLE001 - deletion must not break the request
        logger.warning("Could not delete stored file for attachment %s", attachment.pk,
                       exc_info=True)


def _upload_to_cloudinary(uploaded_file, kind: str, safe_filename: str) -> dict:
    import cloudinary.uploader

    stem = os.path.splitext(safe_filename)[0]
    resource_type = "image" if kind == "image" else "raw"
    folder = "{}/{}s".format(settings.CLOUDINARY_FOLDER, kind)
    # Unique public id so re-uploading the same filename never overwrites.
    public_id = "{}-{}".format(stem, uuid.uuid4().hex[:8])
    if resource_type == "raw":
        # Raw assets keep their extension so downloads open in the right app.
        public_id += os.path.splitext(safe_filename)[1]

    uploaded_file.seek(0)
    result = cloudinary.uploader.upload(
        uploaded_file,
        folder=folder,
        public_id=public_id,
        resource_type=resource_type,
        overwrite=False,
        unique_filename=False,
        use_filename=False,
        invalidate=True,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "resource_type": result.get("resource_type", resource_type),
        "storage_backend": "cloudinary",
        "size": result.get("bytes", getattr(uploaded_file, "size", 0)),
        "width": result.get("width"),
        "height": result.get("height"),
    }


def _upload_to_local(uploaded_file, kind: str, safe_filename: str) -> dict:
    stem, ext = os.path.splitext(safe_filename)
    key = "{}s/{}-{}{}".format(kind, stem, uuid.uuid4().hex[:8], ext)
    uploaded_file.seek(0)
    stored_key = default_storage.save(key, uploaded_file)

    width = height = None
    if kind == "image":
        try:
            from PIL import Image

            uploaded_file.seek(0)
            with Image.open(uploaded_file) as img:
                width, height = img.size
        except Exception:  # noqa: BLE001
            pass

    return {
        "url": default_storage.url(stored_key),
        "public_id": stored_key,
        "resource_type": "image" if kind == "image" else "raw",
        "storage_backend": "local",
        "size": getattr(uploaded_file, "size", 0),
        "width": width,
        "height": height,
    }
