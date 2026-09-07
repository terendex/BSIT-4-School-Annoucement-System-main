"""Deployment sanity checks surfaced by `manage.py check` and on startup."""
import sys

from django.conf import settings
from django.core.checks import Error, Warning, register

# Commands that run with DEBUG off but are not a live deployment, so the
# persistence check below must stay quiet for them:
#   collectstatic - the image build runs it with DJANGO_DEBUG=False and no
#                   database on purpose (see the Dockerfile). Firing here would
#                   fail the build rather than the misconfigured deploy.
#   test          - Django forces DEBUG=False and a throwaway SQLite database
#                   for the test run, which is exactly what the check hunts for.
NON_SERVING_COMMANDS = {"collectstatic", "test"}


def _is_non_serving_command() -> bool:
    return any(command in sys.argv for command in NON_SERVING_COMMANDS)


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
    """Refuse to run production against SQLite inside the container.

    With DATABASE_URL unset the settings fall back to a SQLite file next to the
    code. That works - migrations apply, posts save - right up until the next
    deploy replaces the container and every announcement disappears.

    This is an Error rather than a Warning on purpose. `manage.py migrate` runs
    the system checks and aborts on an Error, and the start command chains
    gunicorn behind it with `&&`, so a service missing DATABASE_URL fails its
    deploy loudly - leaving the previous deploy and its data untouched -
    instead of quietly serving from a database that is about to be discarded.
    """
    if settings.DEBUG or _is_non_serving_command():
        return []
    engine = settings.DATABASES["default"]["ENGINE"]
    if "sqlite" not in engine:
        return []
    return [
        Error(
            "Running on SQLite in production: every announcement would be lost "
            "on the next deploy, because the file lives inside the container.",
            hint=(
                "Set DATABASE_URL on this service to the Postgres reference, "
                "e.g. ${{Postgres.DATABASE_URL}} on Railway. To run a "
                "production-mode container on SQLite anyway, set "
                "DJANGO_DEBUG=True."
            ),
            id="announcements.E002",
        )
    ]
