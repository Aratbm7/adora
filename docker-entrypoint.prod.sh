#!/usr/bin/env bash

# Print a message indicating that the script is waiting for the PostgreSQL database to start
echo "Waiting for postgres db to start.."

# Wait for the PostgreSQL database to be available
./wait-for-it.sh db:5432 --timeout=30 --strict -- echo "PostgreSQL is up - continuing"
./wait-for-it.sh redis:6379 --timeout=30 --strict -- echo "Redis is up - continuing"

# Print a message indicating that Django migrations are being made
echo "Making migrations for Django"
python manage.py makemigrations adora
python manage.py makemigrations account
python manage.py makemigrations 


# Print a message indicating that Django migrations are being applied to the PostgreSQL database
echo "Applying migrations to PostgreSQL database"
python manage.py migrate --noinput


echo "Collect static files"
python manage.py collectstatic --noinput

# Print a message indicating that the Django development server is starting on port 8000



# Set the number of workers
NUM_WORKERS=3

# Bind Gunicorn to a Unix socket
SOCKET_PATH="/run/gunicorn.sock"

# Django project's WSGI application
WSGI_APPLICATION="core.wsgi:application"

if [ ! -d "$SOCKET_DIR" ]; then
    mkdir -p "$SOCKET_DIR"
fi

# Ensure the socket path does not exist from previous runs
if [ -e "$SOCKET_PATH" ]; then
    rm -f "$SOCKET_PATH"
fi

# Print a message indicating the Gunicorn server is starting
echo "Running Django Production server with Gunicorn"

echo "Starting Gunicorn with $NUM_WORKERS workers, binding to $SOCKET_PATH"
exec gunicorn --workers $NUM_WORKERS --bind unix:$SOCKET_PATH $WSGI_APPLICATION \
    --user adora_u --group adora_g 
# exec gunicorn core.wsgi:application --bind unix:/run/gunicorn.sock --workers 3 --log-level debug
