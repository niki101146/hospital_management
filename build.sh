#!/usr/bin/env bash
# Render build script
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py makemigrations hms --no-input
python manage.py migrate --no-input
python manage.py setup_demo
