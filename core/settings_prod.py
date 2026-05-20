import os
from .settings import *

DEBUG = True

ALLOWED_HOSTS = ['bingo-cotonete.onrender.com']

CSRF_TRUSTED_ORIGINS = ['https://bingo-cotonete.onrender.com']

SECRET_KEY = os.environ.get('SECRET_KEY')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PGDATABASE'),
        'USER': os.environ.get('PGUSER'),
        'PASSWORD': os.environ.get('PGPASSWORD'),
        'HOST': os.environ.get('PGHOST'),
        'PORT': os.environ.get('PGPORT', '5432'),
    }
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
SITE_ID = 1


from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
Site.objects.update_or_create(id=1, defaults={'domain': 'localhost:8001', 'name': 'localhost'})
site = Site.objects.get(id=1)
if not SocialApp.objects.filter(provider='discord').exists():
    app = SocialApp.objects.create(
        provider='discord',
        name='Discord',
        client_id='1502749650828918874',
        secret='VMRaVhyafsPJRWuh354dv_sFwntPqT8C',

    )
    app.sites.add(site)
    print('Criado!')