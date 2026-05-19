#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input --settings=core.settings_prod
python manage.py migrate --settings=core.settings_prod
python manage.py shell --settings=core.settings_prod -c "
from django.contrib.sites.models import Site
Site.objects.update_or_create(id=1, defaults={'domain': 'bingo-cotonete.onrender.com', 'name': 'bingo-cotonete'})
"