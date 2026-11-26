import os

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def configurar_site(using, **kwargs):
    """Grava o domínio do Site (allauth monta as URLs de retorno com ele). Idempotente.

    Só age com DJANGO_SITE_DOMAIN definido, então roda na etapa de migração do piloto e não
    muda a instalação atual, cujo entrypoint.sh grava o próprio domínio.
    """
    domain = os.environ.get('DJANGO_SITE_DOMAIN', '').strip()
    if not domain:
        return
    from django.conf import settings
    from django.contrib.sites.models import Site

    Site.objects.using(using).update_or_create(
        id=settings.SITE_ID, defaults={'domain': domain, 'name': 'bingo-cotonete'}
    )


class BingoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bingo"

    def ready(self):
        post_migrate.connect(configurar_site, sender=self)
