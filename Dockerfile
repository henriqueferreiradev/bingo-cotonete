FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# O .dockerignore mantém fora .env*, bancos locais, backups, venv e staticfiles/ do host.
COPY . .
RUN chmod +x /app/entrypoint.sh

# Estáticos ficam dentro da imagem e são servidos pelo WhiteNoise (os slots não montam volume).
RUN python manage.py collectstatic --no-input --settings=core.settings_prod

# SHA do commit, passado pelo CI (--build-arg APP_COMMIT=<sha>) e devolvido em /version.
ARG APP_COMMIT=""
ENV APP_COMMIT=${APP_COMMIT}
LABEL org.opencontainers.image.revision=${APP_COMMIT}

EXPOSE 8002

# Processo dos slots blue/green da Central: Gunicorn em 8002 com core.settings_prod.
# Migrações rodam antes, em etapa separada do executor (migrate_command do alvo).
# O docker-compose.yml da instalação atual substitui este CMD por /app/entrypoint.sh.
CMD ["gunicorn", "core.wsgi:application", \
     "--bind", "0.0.0.0:8002", \
     "--workers", "2", \
     "--env", "DJANGO_SETTINGS_MODULE=core.settings_prod", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
