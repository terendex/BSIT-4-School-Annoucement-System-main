# Same image as the root Dockerfile, but for a build context of backend/.
#
# Railway's "Root Directory" setting decides which of the two is used:
#   Root Directory = /         -> ../Dockerfile        (context = repo root)
#   Root Directory = backend   -> this file            (context = backend/)
# Having both means the service builds correctly on either setting.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Requirements first so ordinary code edits reuse the cached install layer.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Bake static files into the image for WhiteNoise. No database or real secret
# is needed here - the placeholder key only lets settings import.
RUN DJANGO_SECRET_KEY=build-time-only-not-a-secret \
    DJANGO_DEBUG=False \
    python manage.py collectstatic --no-input --clear

EXPOSE 8000

CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60"]
