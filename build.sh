#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input --settings=core.settings_prod

python manage.py migrate --settings=core.settings_prod

python manage.py shell --settings=core.settings_prod -c "
import os
from django.contrib.sites.models import Site
from django.contrib.auth.models import User

Site.objects.update_or_create(id=1, defaults={'domain': 'bingo-cotonete.onrender.com', 'name': 'bingo-cotonete'})
print('Site configurado')

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
if password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print('Superuser criado')
else:
    print('Superuser ja existe ou senha nao definida')
"

python manage.py shell --settings=core.settings_prod -c "
import requests, os
r = requests.post('https://discord.com/api/oauth2/token', data={
    'client_id': os.environ.get('DISCORD_CLIENT_ID'),
    'client_secret': os.environ.get('DISCORD_SECRET'),
    'grant_type': 'client_credentials',
    'scope': 'identify'
})
print('Discord API status:', r.status_code)
print('Discord API response:', r.json())
"