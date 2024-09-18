#!/usr/bin/env bash

echo "Waiting for postgres db to start.."

# Wait for the PostgreSQL database to be available
./wait-for-it.sh db:5432 --timeout=30 --strict -- echo "PostgreSQL is up - continuing"
./wait-for-it.sh redis_master:6379 --timeout=30 --strict -- echo "Redis Master is up - continuing"
./wait-for-it.sh redis_replica:6380 --timeout=30 --strict -- echo "Redis Replica is up - continuing"


echo "Running celery worker"
celery -A core worker -l info