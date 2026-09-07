"""Deployment sanity checks surfaced by `manage.py check` and on startup."""
from django.conf import settings
from django.core.checks import Warning, register


@register()
def cloudinary_configured_in_production(app_configs, **kwargs):
    """Warn when uploads would land on an ephemeral container filesystem.

    Without Cloudinary credentials the storage layer falls back to MEDIA_ROOT,
    which on Railway or Render lives inside the container: the files are not
    served in production (so images render broken) and they are destroyed on
    the next deploy. Silent data loss, so it is worth shouting about.
    """
    if settings.DEBUG or settings.CLOUDINARY_ENABLED:
        return []
    missing = [
        name
        for name, value in (
            ("CLOUDINARY_CLOUD_NAME", settings.CLOUDINARY_CLOUD_NAME),
            ("CLOUDINARY_API_KEY", settings.CLOUDINARY_API_KEY),
            ("CLOUDINARY_API_SECRET", settings.CLOUDINARY_API_SECRET),
        )
        if not value
    ]
    return [
        Warning(
            "Cloudinary is not configured; uploads will be written to the "
            "container filesystem, will not be served, and will be lost on the "
            "next deploy.",
            hint="Set " + ", ".join(missing) + " in the service's variables.",
            id="announcements.W001",
        )
    ]


@register()
def database_is_persistent_in_production(app_configs, **kwargs):
    """Warn when production is running on SQLite inside the container.

    With DATABASE_URL unset the settings fall back to a SQLite file next to the
    code. That works - migrations apply, posts save - right up until the next
    deploy replaces the container and every announcement disappears.
    """
    if settings.DEBUG:
        return []
    engine = settings.DATABASES["default"]["ENGINE"]
    if "sqlite" not in engine:
        return []
    return [
        Warning(
            "Running on SQLite in production: every announcement will be lost "
            "on the next deploy, because the file lives inside the container.",
            hint=(
                "Set DATABASE_URL on this service to the Postgres reference, "
                "e.g. ${{Postgres.DATABASE_URL}} on Railway."
            ),
            id="announcements.W002",
        )
    ]
