from rest_framework.throttling import UserRateThrottle


class UploadRateThrottle(UserRateThrottle):
    """Caps how fast the admin can push files at Cloudinary."""

    scope = "upload"
