import os
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .settings import *

DEBUG = False


def _env_list(name, default):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# Padrões = instalação atual. O piloto define o próprio domínio no arquivo de variáveis.
ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', 'bingo.kordan.tech')

CSRF_TRUSTED_ORIGINS = _env_list('DJANGO_CSRF_TRUSTED_ORIGINS', 'https://bingo.kordan.tech')

# Nginx on the host terminates SSL and forwards requests as HTTP internally.
# Without this, request.build_absolute_uri() returns http://, so allauth sends
# redirect_uri=http://... to Discord while the Developer Portal has https://...
# registered → Discord token exchange returns 401.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

SECRET_KEY = os.environ.get('SECRET_KEY')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
# O executor da Central injeta KORDAN_RELEASE_VERSION nos slots e no contêiner de migração.
# Ali o SQLite ficaria dentro de cada contêiner (um banco por slot, perdido na troca).
if os.environ.get('KORDAN_RELEASE_VERSION') and not DATABASE_URL:
    raise ImproperlyConfigured(
        'DATABASE_URL é obrigatório quando o Bingo roda pela Central de Deploy '
        '(KORDAN_RELEASE_VERSION definido). Configure o PostgreSQL do ambiente no env_file do alvo.'
    )
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
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

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'allauth': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'requests': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        # Tracebacks de erro 500 no stdout do contêiner (o executor mostra os logs do slot).
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
    },
}

SOCIALACCOUNT_PROVIDERS = {
    'discord': {
        'SCOPE': ['identify', 'email'],
    }
}
# A instalação atual guarda o app do Discord no banco (SocialApp). O piloto, com banco novo,
# recebe o app pelo env_file. Não defina as duas coisas no mesmo ambiente.
if os.environ.get('DISCORD_CLIENT_ID'):
    SOCIALACCOUNT_PROVIDERS['discord']['APPS'] = [{
        'client_id': os.environ['DISCORD_CLIENT_ID'],
        'secret': os.environ.get('DISCORD_CLIENT_SECRET', ''),
    }]

ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_EMAIL_REQUIRED = False
SOCIALACCOUNT_EMAIL_REQUIRED = False
LOGIN_REDIRECT_URL = '/cartela/'

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
SOCIALACCOUNT_ADAPTER = 'bingo.adapters.MySocialAccountAdapter'

SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True