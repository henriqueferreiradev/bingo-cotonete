"""Rotas operacionais usadas pela Central de Deploy da Kordan.

/healthz e /version não dependem de sessão nem de login e nunca expõem detalhes internos.
"""

import logging
import os

from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)

# Depois que um processo confirma que não há migrações pendentes, não carrega o grafo de novo:
# migrações só avançam (expand/contract), então o resultado positivo continua válido.
_migrations_applied = False


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


def _pending_migrations():
    executor = MigrationExecutor(connection)
    return bool(executor.migration_plan(executor.loader.graph.leaf_nodes()))


@require_safe
def healthz(request):
    global _migrations_applied
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        if not _migrations_applied:
            if _pending_migrations():
                logger.warning("healthz: há migrações pendentes")
                return _no_store(HttpResponse("unavailable", status=503, content_type="text/plain"))
            _migrations_applied = True
    except DatabaseError:
        logger.warning("healthz: banco indisponível", exc_info=True)
        return _no_store(HttpResponse("unavailable", status=503, content_type="text/plain"))
    return _no_store(HttpResponse("ok", content_type="text/plain"))


@require_safe
def version(request):
    # Fora da Central (execução local, imagem sem build-arg) os campos valem "local".
    return _no_store(JsonResponse({
        "version": os.environ.get("KORDAN_RELEASE_VERSION") or "local",
        "commit": os.environ.get("APP_COMMIT") or "local",
        "slot": os.environ.get("KORDAN_SLOT") or "local",
    }))
