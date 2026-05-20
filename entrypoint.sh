#!/bin/bash
set -e

python manage.py migrate --settings=core.settings_prod

python manage.py shell --settings=core.settings_prod << 'PYEOF'
import os
from django.contrib.sites.models import Site
from django.contrib.auth.models import User

Site.objects.update_or_create(id=1, defaults={'domain': 'bingo.kordan.tech', 'name': 'bingo-cotonete'})

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
if password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print('Superuser criado')
else:
    print('Superuser ja existe')
PYEOF

exec gunicorn core.wsgi:application --bind 0.0.0.0:8002 --workers 2 --access-logfile - --error-logfile -

