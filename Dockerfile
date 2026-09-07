# Builds the Django API. Living at the repo root means Railway builds it with
# the default Root Directory ("/"), so the service works on a fresh deploy with
# no dashboard configuration to set or lose.
#
# The frontend is not built here - it deploys separately to Vercel.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Requirements first: this layer is cached unless requirements.txt changes,
# so ordinary code edits rebuild in seconds.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Bake the static files into the image. WhiteNoise serves them at runtime, and
# its manifest storage needs this to have run. No database or real secrets are
# touched here - the placeholder key is only used to import settings.
RUN DJANGO_SECRET_KEY=build-time-only-not-a-secret \
    DJANGO_DEBUG=False \
    python manage.py collectstatic --no-input --clear

EXPOSE 8000

# Railway injects PORT; the fallback keeps `docker run` working locally.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60"]
