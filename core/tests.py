import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings

from core import ops


class HealthzTests(TestCase):
    def setUp(self):
        ops._migrations_applied = False

    def test_saudavel(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("Set-Cookie", response.headers)

    def test_banco_indisponivel(self):
        with mock.patch("core.ops.connection") as connection:
            connection.cursor.side_effect = OperationalError("could not connect to server: senha=segredo")
            with self.assertLogs("core.ops", "WARNING"):
                response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"unavailable")

    def test_migracoes_pendentes(self):
        with mock.patch("core.ops._pending_migrations", return_value=True), self.assertLogs("core.ops", "WARNING"):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(ops._migrations_applied)

    def test_grafo_de_migracoes_carregado_uma_vez(self):
        with mock.patch("core.ops._pending_migrations", return_value=False) as pending:
            self.client.get("/healthz")
            self.client.get("/healthz")
        self.assertEqual(pending.call_count, 1)

    def test_sem_pendencias_no_banco_de_teste(self):
        self.assertFalse(ops._pending_migrations())

    def test_metodo_nao_permitido(self):
        self.assertEqual(self.client.post("/healthz").status_code, 405)


class VersionTests(TestCase):
    def test_metadados_da_central(self):
        env = {"KORDAN_RELEASE_VERSION": "1.0.7", "KORDAN_SLOT": "green", "APP_COMMIT": "a" * 40}
        with mock.patch.dict(os.environ, env):
            response = self.client.get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"version": "1.0.7", "commit": "a" * 40, "slot": "green"})
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("Set-Cookie", response.headers)

    def test_execucao_local(self):
        with mock.patch.dict(os.environ, {"KORDAN_RELEASE_VERSION": "", "KORDAN_SLOT": "", "APP_COMMIT": ""}):
            response = self.client.get("/version")
        self.assertEqual(response.json(), {"version": "local", "commit": "local", "slot": "local"})

    def test_sem_barra_final_e_sem_redirecionamento(self):
        self.assertEqual(self.client.get("/version").status_code, 200)
        self.assertEqual(self.client.get("/version/").status_code, 404)


class SiteTests(TestCase):
    def test_dominio_configuravel_e_idempotente(self):
        with mock.patch.dict(os.environ, {"DJANGO_SITE_DOMAIN": "bingo-piloto.example.com"}):
            call_command("migrate", verbosity=0)
            call_command("migrate", verbosity=0)
        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(Site.objects.get(id=settings.SITE_ID).domain, "bingo-piloto.example.com")

    def test_sem_variavel_nao_altera(self):
        Site.objects.update_or_create(id=settings.SITE_ID, defaults={"domain": "bingo.kordan.tech"})
        with mock.patch.dict(os.environ, {"DJANGO_SITE_DOMAIN": ""}):
            call_command("migrate", verbosity=0)
        self.assertEqual(Site.objects.get(id=settings.SITE_ID).domain, "bingo.kordan.tech")


class PaginaInicialTests(TestCase):
    @override_settings(SOCIALACCOUNT_PROVIDERS={"discord": {"APPS": [{"client_id": "piloto", "secret": "x"}]}})
    def test_app_do_discord_pelas_configuracoes(self):
        # Banco do piloto sem SocialApp: o app vem do env_file (DISCORD_CLIENT_ID).
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/accounts/discord/login/")


class SettingsProdTests(TestCase):
    """Importa core.settings_prod num processo limpo, como um contêiner faria."""

    def run_settings(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("KORDAN_", "DJANGO_")) and k != "DATABASE_URL"}
        env.update(DJANGO_SETTINGS_MODULE="core.settings_prod", PYTHONIOENCODING="utf-8", **extra)
        code = ("from django.conf import settings; "
                "print(settings.ALLOWED_HOSTS, settings.CSRF_TRUSTED_ORIGINS, settings.DATABASES['default']['ENGINE'])")
        return subprocess.run([sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)

    def test_pela_central_sem_database_url_falha(self):
        result = self.run_settings(KORDAN_RELEASE_VERSION="1.0.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL é obrigatório", result.stderr)

    def test_demais_ambientes_preservados(self):
        result = self.run_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         "['bingo.kordan.tech'] ['https://bingo.kordan.tech'] django.db.backends.sqlite3")

    def test_dominio_do_piloto(self):
        result = self.run_settings(
            KORDAN_RELEASE_VERSION="1.0.0", DATABASE_URL="postgres://u:p@db:5432/bingo",
            DJANGO_ALLOWED_HOSTS="bingo-piloto.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://bingo-piloto.example.com",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         "['bingo-piloto.example.com'] ['https://bingo-piloto.example.com'] "
                         "django.db.backends.postgresql")
