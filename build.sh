#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input --settings=core.settings_prod

python manage.py migrate --settings=core.settings_prod

python manage.py shell --settings=core.settings_prod -c "
import os
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.contrib.auth.models import User

# Site
Site.objects.update_or_create(id=1, defaults={'domain': 'bingo-cotonete.onrender.com', 'name': 'bingo-cotonete'})
print('Site configurado')

# SocialApp Discord
site = Site.objects.get(id=1)
if not SocialApp.objects.filter(provider='discord').exists():
    app = SocialApp.objects.create(
        provider='discord',
        name='Discord',
        client_id=os.environ.get('DISCORD_CLIENT_ID'),
        secret=os.environ.get('DISCORD_SECRET'),
    )
    app.sites.add(site)
    print('SocialApp Discord criado')
else:
    print('SocialApp Discord ja existe')

# Superuser
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
if password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print('Superuser criado')
else:
    print('Superuser ja existe ou senha nao definida')
"