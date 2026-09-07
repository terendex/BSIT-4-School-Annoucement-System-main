"""Upload validation: extension + MIME allowlists, size caps, filename sanitising."""
import os
import re

from django.conf import settings
from rest_framework import serializers

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

FILE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".csv",
    ".zip",
}
FILE_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",  # some browsers send this for .docx/.zip
}

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, fallback: str = "upload") -> str:
    """Strip directory parts and anything outside a conservative charset."""
    name = os.path.basename(name or "")
    name = name.replace("\\", "/").split("/")[-1]
    stem, ext = os.path.splitext(name)
    stem = _UNSAFE_CHARS.sub("-", stem).strip("-._")[:100] or fallback
    ext = _UNSAFE_CHARS.sub("", ext.lower())[:10]
    return stem + ext


def _human(size: int) -> str:
    return "{:.1f} MB".format(size / (1024 * 1024))


def validate_upload(uploaded_file, kind: str):
    """Validate one upload and return its sanitised filename.

    Raises rest_framework.serializers.ValidationError on any failure.
    """
    if kind not in {"image", "file"}:
        raise serializers.ValidationError({"kind": "Must be 'image' or 'file'."})

    filename = sanitize_filename(getattr(uploaded_file, "name", ""))
    ext = os.path.splitext(filename)[1].lower()
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    size = getattr(uploaded_file, "size", 0) or 0

    if kind == "image":
        allowed_ext, allowed_mime = IMAGE_EXTENSIONS, IMAGE_MIME_TYPES
        max_size = settings.MAX_IMAGE_UPLOAD_SIZE
    else:
        allowed_ext, allowed_mime = FILE_EXTENSIONS, FILE_MIME_TYPES
        max_size = settings.MAX_FILE_UPLOAD_SIZE

    if size <= 0:
        raise serializers.ValidationError({"file": "The uploaded file is empty."})
    if size > max_size:
        raise serializers.ValidationError(
            {"file": "File is {} - the limit is {}.".format(_human(size), _human(max_size))}
        )
    if ext not in allowed_ext:
        raise serializers.ValidationError(
            {"file": "Extension '{}' is not allowed. Allowed: {}.".format(
                ext or "(none)", ", ".join(sorted(allowed_ext))
            )}
        )
    if content_type and content_type not in allowed_mime:
        raise serializers.ValidationError(
            {"file": "Content type '{}' is not allowed.".format(content_type)}
        )

    if kind == "image":
        _verify_image_bytes(uploaded_file)

    return filename


def _verify_image_bytes(uploaded_file):
    """Confirm the bytes really are a decodable image, not just a renamed file."""
    from PIL import Image, UnidentifiedImageError

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise serializers.ValidationError(
            {"file": "That file is not a readable image."}
        )
    finally:
        uploaded_file.seek(0)
