#!/usr/bin/env bash
echo "Waiting for postgres db to start.."

# Wait for the PostgreSQL database to be available
./wait-for-it.sh db:5432 --timeout=30 --strict -- echo "PostgreSQL is up - continuing"
./wait-for-it.sh redis:6379 --timeout=30 --strict -- echo "Redis is up - continuing"

echo "Collect static files"
python manage.py collectstatic --noinput

echo "Running celery flower"
celery -A core flower --basic-auth=mmd:6688