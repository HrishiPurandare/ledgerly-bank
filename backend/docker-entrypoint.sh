#!/bin/sh
# Runs before the server starts: database up to date, demo data present (only when asked for).
set -e

python manage.py migrate --noinput

if [ "$LEDGERLY_SEED_ON_START" = "true" ]; then
  # Idempotent: seed only when the demo customers don't exist yet, so restarts keep your changes.
  python manage.py shell -c "from django.contrib.auth import get_user_model as U; import sys; sys.exit(0 if U().objects.filter(email='sara@example.com').exists() else 1)" \
    || python manage.py seed
fi

exec "$@"
