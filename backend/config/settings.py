"""Django settings for the Class Announcement System."""
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list:
    raw = os.getenv(name, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# The platform supplies the service's own hostname; add it so Django answers
# there without DJANGO_ALLOWED_HOSTS having to be edited on every redeploy.
# RAILWAY_PUBLIC_DOMAIN is set by Railway, RENDER_EXTERNAL_HOSTNAME by Render.
PLATFORM_HOSTNAMES = [
    host
    for host in (
        os.getenv("RAILWAY_PUBLIC_DOMAIN"),
        os.getenv("RAILWAY_PRIVATE_DOMAIN"),
        os.getenv("RENDER_EXTERNAL_HOSTNAME"),
    )
    if host
]
ALLOWED_HOSTS.extend(PLATFORM_HOSTNAMES)

# Service-to-service calls inside Railway use *.railway.internal rather than
# the public domain. Healthchecks are handled by HealthCheckMiddleware, which
# runs before this list is ever consulted.
if os.getenv("RAILWAY_ENVIRONMENT_NAME") or os.getenv("RAILWAY_PRIVATE_DOMAIN"):
    ALLOWED_HOSTS.append(".railway.internal")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "announcements",
]

MIDDLEWARE = [
    # First on purpose: answers /healthz/ without touching the Host header,
    # so platform healthchecks cannot be broken by ALLOWED_HOSTS or the HTTPS
    # redirect. See config/middleware.py.
    "config.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database - Postgres in production, SQLite locally when DATABASE_URL is unset
# --------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# A platform reference like ${{Postgres.DATABASE_URL}} resolves to an empty
# string when the service name does not match, which looks identical to
# "never set". Keep the raw value so the checks can tell them apart.
DATABASE_URL_RAW = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    # A reference the platform failed to substitute arrives here as literal
    # text, and dj_database_url reports it as "No support for ''" from three
    # frames deep - a traceback that says nothing about what to go and fix.
    if "${" in DATABASE_URL or DATABASE_URL.startswith("<"):
        raise ImproperlyConfigured(
            "DATABASE_URL is the literal text {!r}; the platform did not "
            "substitute it. On Railway the name inside ${{...}} is the database "
            "SERVICE name - if your Postgres service is not called 'Postgres', "
            "the reference has to match whatever it is actually called. Pasting "
            "the database's own DATABASE_URL value literally works too.".format(
                DATABASE_URL
            )
        )
    if "://" not in DATABASE_URL:
        raise ImproperlyConfigured(
            "DATABASE_URL does not look like a connection URL: {!r}. It should "
            "start with postgres:// (or sqlite:///).".format(DATABASE_URL)
        )

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL, conn_max_age=600, conn_health_checks=True
        )
    }
    # TLS mode. "require" fails outright against a server that does not offer
    # SSL - which is the case for Railway Postgres over its private network,
    # while managed hosts reached over the internet do offer it. "prefer"
    # encrypts whenever the server supports it and connects either way, so one
    # setting is correct on both. Set DATABASE_SSL_REQUIRE=True to insist.
    # Postgres only: sqlite3 and mysql reject an sslmode connection argument
    # outright, which made a sqlite:/// DATABASE_URL - handy for a one-off
    # restore or a throwaway copy - fail to connect at all.
    if DATABASES["default"].get("ENGINE", "").endswith(
        ("postgresql", "postgresql_psycopg2")
    ) and "sslmode" not in DATABASE_URL:
        sslmode = "require" if env_bool("DATABASE_SSL_REQUIRE", False) else "prefer"
        DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = sslmode
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Passwords - Argon2 first, PBKDF2 kept so older hashes still verify
# --------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "announcements.passwords.ComplexityValidator"},
    {"NAME": "announcements.passwords.CommonPasswordVariationValidator"},
]

# --------------------------------------------------------------------------
# I18N / static / media
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Only used as the local-dev fallback when Cloudinary is not configured.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --------------------------------------------------------------------------
# Cloudinary
# --------------------------------------------------------------------------
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "announcements").strip()
CLOUDINARY_ENABLED = all(
    [CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]
)

if CLOUDINARY_ENABLED:
    import cloudinary

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

# --------------------------------------------------------------------------
# Email - Gmail SMTP, used to send publisher invites
# --------------------------------------------------------------------------
# EMAIL_HOST_PASSWORD must be a Google "App Password" (16 characters, generated
# at myaccount.google.com/apppasswords with 2-Step Verification on). A normal
# Gmail password will be refused by the SMTP server.
SITE_NAME = os.getenv("SITE_NAME", "SLC Announcements").strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))

# Brevo over HTTPS, preferred when a key is present.
#
# Container hosts generally block outbound SMTP - on Railway the symptom is
# "OSError: [Errno 101] Network is unreachable" against port 587, which no
# credential can fix. Brevo's HTTP API goes over 443 and works from there.
# The key must be an API key (xkeysib-...), not an SMTP key (xsmtpsib-...).
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()

SMTP_CONFIGURED = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
EMAIL_ENABLED = bool(BREVO_API_KEY or SMTP_CONFIGURED)

if BREVO_API_KEY:
    EMAIL_BACKEND = "announcements.mail_backends.BrevoAPIBackend"
elif SMTP_CONFIGURED:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    # Nothing configured: print invites to the console rather than failing.
    # Local development works, and announcements.checks warns if this is live.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Brevo requires the sender to be an address verified in the account.
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip() or EMAIL_HOST_USER
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "{} <{}>".format(SITE_NAME, EMAIL_SENDER) if EMAIL_SENDER else "webmaster@localhost",
)

# How long a mailed temporary password stays usable.
INVITE_EXPIRY_DAYS = int(os.getenv("INVITE_EXPIRY_DAYS", "7"))

# Mail everyone with an account when a post goes up or its wording changes.
# Set ANNOUNCEMENT_EMAILS=false to keep the invites but stop the notifications
# - during a bulk import, say, where every restored row would mail the staff.
ANNOUNCEMENT_EMAILS = env_bool("ANNOUNCEMENT_EMAILS", True)

# --------------------------------------------------------------------------
# Upload limits (also enforced per file in announcements/validators.py)
# --------------------------------------------------------------------------
MAX_IMAGE_UPLOAD_SIZE = int(os.getenv("MAX_IMAGE_UPLOAD_SIZE", 5 * 1024 * 1024))
MAX_FILE_UPLOAD_SIZE = int(os.getenv("MAX_FILE_UPLOAD_SIZE", 10 * 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_FILE_UPLOAD_SIZE + (1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# --------------------------------------------------------------------------
# DRF + JWT
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "announcements.pagination.StandardPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        # Brute-force protection on the admin login endpoint.
        "login": os.getenv("LOGIN_THROTTLE_RATE", "5/min"),
        # Changing your own password: authenticated, and the current password
        # is required, so the tight login budget would only punish typos.
        "password": os.getenv("PASSWORD_THROTTLE_RATE", "20/min"),
        "public": os.getenv("PUBLIC_THROTTLE_RATE", "120/min"),
        "upload": os.getenv("UPLOAD_THROTTLE_RATE", "60/min"),
    },
    "EXCEPTION_HANDLER": "announcements.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --------------------------------------------------------------------------
# CORS / CSRF - locked to the Vercel frontend
# --------------------------------------------------------------------------
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:4321").rstrip("/")
CORS_ALLOWED_ORIGINS = [FRONTEND_ORIGIN] + [
    o.rstrip("/") for o in env_list("EXTRA_CORS_ORIGINS")
]
CORS_ALLOW_CREDENTIALS = False  # JWT rides in the Authorization header, not cookies.
CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-requested-with",
]

# Vercel preview deployments (optional).
if env_bool("ALLOW_VERCEL_PREVIEWS", False):
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://[a-z0-9-]+\.vercel\.app$"]

CSRF_TRUSTED_ORIGINS = [o for o in CORS_ALLOWED_ORIGINS if o.startswith("https://")]
CSRF_TRUSTED_ORIGINS.extend("https://" + host for host in PLATFORM_HOSTNAMES)

# --------------------------------------------------------------------------
# Security headers
# --------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
# Platform healthchecks (Railway, Render) call the container over plain HTTP.
# Without this they would receive a 301 to https and mark the deploy unhealthy.
SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
if "test" in sys.argv:
    # The test client speaks plain HTTP; redirecting would 301 every request.
    SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"}
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
