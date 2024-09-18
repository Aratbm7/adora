#!/usr/bin/env bash

# Print a message indicating that the script is waiting for the PostgreSQL database to start
echo "Waiting for postgres db to start.."

# Wait for the PostgreSQL database to be available
./wait-for-it.sh db:5432 --timeout=30 --strict -- echo "PostgreSQL is up - continuing"
./wait-for-it.sh redis_master:6379 --timeout=30 --strict -- echo "Redis Master is up - continuing"
./wait-for-it.sh redis_replica:6380 --timeout=30 --strict -- echo "Redis Replica is up - continuing"



# Print a message indicating that Django migrations are being made
echo "Making migrations for Django"
python manage.py makemigrations adora
python manage.py makemigrations account
python manage.py makemigrations 

# python manage.py flush --no-input

# Print a message indicating that Django migrations are being applied to the PostgreSQL database
echo "Applying migrations to PostgreSQL database"
python manage.py migrate --no-input

echo "Collect static files"
python manage.py collectstatic --noinput

# Print a message indicating that the Django development server is starting on port 8000
echo "Running Django development server on port 8000"
python manage.py runserver 0.0.0.0:8000 
