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


def _sqlite_hint() -> str:
    """Say which of the two ways DATABASE_URL went missing actually happened."""
    raw = getattr(settings, "DATABASE_URL_RAW", "")

    if "${{" in raw or "${" in raw:
        return (
            "DATABASE_URL is set to the literal text {!r} - the platform did "
            "not substitute it. On Railway the name inside the reference is the "
            "database SERVICE name: if your Postgres service is not called "
            "'Postgres', the reference must match whatever it is called.".format(raw)
        )

    if raw and not raw.strip():
        return "DATABASE_URL is set but contains only whitespace."

    return (
        "DATABASE_URL is empty or unset on this service. On Railway, add the "
        "Postgres database, then set DATABASE_URL on THIS service to "
        "${{Postgres.DATABASE_URL}} - and check the name inside those braces "
        "matches your database service exactly, because a reference that does "
        "not resolve is delivered as an empty string with no warning. Pasting "
        "the database's own DATABASE_URL value literally works too. To run a "
        "production-mode container on SQLite anyway, set DJANGO_DEBUG=True."
    )


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
            hint=_sqlite_hint(),
            id="announcements.E002",
        )
    ]


@register()
def email_configured_in_production(app_configs, **kwargs):
    """Warn when publisher invites would be printed instead of sent.

    Without EMAIL_HOST_USER / EMAIL_HOST_PASSWORD the console backend is used:
    inviting a publisher appears to work, but the temporary password goes to
    the container's log rather than to their inbox, so they can never sign in.
    """
    if settings.DEBUG or settings.EMAIL_ENABLED or _is_non_serving_command():
        return []
    return [
        Warning(
            "Email is not configured; publisher invites will not be delivered "
            "and the temporary password will be written to the deploy log.",
            hint=(
                "Set BREVO_API_KEY to a Brevo API key (xkeysib-...) and "
                "EMAIL_SENDER to a verified sender address. Most hosts block "
                "outbound SMTP, so Gmail's EMAIL_HOST_USER / "
                "EMAIL_HOST_PASSWORD will not work on Railway - the HTTP API "
                "goes over 443 instead."
            ),
            id="announcements.W003",
        )
    ]
