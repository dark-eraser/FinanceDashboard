#!/bin/bash
set -e

echo "FinanceTracker Docker Entrypoint"
echo "================================"

# Change to Django project directory
cd /app/faster

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "Starting server..."
exec "$@"
