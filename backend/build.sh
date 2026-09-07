#!/usr/bin/env bash
# Render build command. Exit on error.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
# Creates/updates the single admin account from ADMIN_* env vars (no-op if unset).
python manage.py ensure_admin
