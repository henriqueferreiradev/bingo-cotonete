#!/usr/bin/env bash
# Valida o Bingo no formato do piloto, sem VPS nem Central: PostgreSQL exclusivo, migração em
# contêiner separado, slots blue/green pelo CMD da imagem e Nginx com HTTPS, trocando o upstream
# com nginx -t + reload como o executor faz. Tudo local, com nomes bingo1-piloto-local-*.
#
#   deploy/piloto/validar_local.sh        sobe, valida e deixa rodando (https://127.0.0.1:18443)
#   deploy/piloto/validar_local.sh down   remove contêineres e rede
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1                       # Git Bash no Windows: não converter caminhos do contêiner
HOST_DIR=$(pwd -W 2>/dev/null || pwd)

P=bingo1-piloto-local
NET=$P DB=$P-db NGINX=$P-nginx WEB=$P-web
IMAGE=bingo-cotonete:piloto-local
DOMAIN=bingo-piloto.kordan.tech
PORT=18443
LOCAL=deploy/piloto/.local
VERSION=0.0.1-local
BASE="https://$DOMAIN:$PORT"

down() { docker rm -f "$WEB-blue" "$WEB-green" "$WEB-migrate" "$NGINX" "$DB" >/dev/null 2>&1 || true
         docker network rm "$NET" >/dev/null 2>&1 || true; }
if [ "${1:-}" = down ]; then down; echo "removido"; exit 0; fi

pass() { echo "  OK   $*"; }
fail() { echo "  FALHA $*"; exit 1; }
expect() { [ "$2" = "$3" ] && pass "$1 ($3)" || fail "$1: esperado $3, veio $2"; }
web() { curl -sk --resolve "$DOMAIN:$PORT:127.0.0.1" "$@"; }
code() { web -o /dev/null -w '%{http_code}' "$@"; }
# GET direto num slot, como o executor (Host = slot_host_header), de dentro da rede Docker.
slot_get() { docker exec "$NGINX" curl -s -o /dev/null -w '%{http_code}' -H "Host: $DOMAIN" "http://$WEB-$1:8002$2"; }
slot_body() { docker exec "$NGINX" curl -s -H "Host: $DOMAIN" "http://$WEB-$1:8002$2"; }
switch_to() {
  sed -e "s/^# kordan-active-slot: .*/# kordan-active-slot: $1/" -e "s/server .*;/server $WEB-$1:8002;/" \
      -e "s/default \"[a-z]*\"/default \"$1\"/" "$LOCAL/upstreams/bingo1-piloto.conf" > "$LOCAL/up.tmp"
  mv "$LOCAL/up.tmp" "$LOCAL/upstreams/bingo1-piloto.conf"
  docker exec "$NGINX" nginx -t -q && docker exec "$NGINX" nginx -s reload
  sleep 1
}

echo "== Build (APP_COMMIT = HEAD)"
COMMIT=$(git rev-parse HEAD)
docker build -q --build-arg APP_COMMIT="$COMMIT" -t "$IMAGE" . >/dev/null
DIGEST=$(docker image inspect -f '{{.Id}}' "$IMAGE")
docker run --rm "$IMAGE" sh -c 'test ! -e /app/db.sqlite3 && test ! -e /app/.env && test ! -e /app/venv && test ! -e /app/.git' \
  && pass "contexto de build sem db.sqlite3, .env, venv e .git" || fail "arquivo privado dentro da imagem"

echo "== Ambiente: rede, PostgreSQL do piloto, variáveis"
down; mkdir -p "$LOCAL/upstreams" "$LOCAL/certs"; rm -f "$LOCAL/upstreams/"*.conf
docker network create "$NET" >/dev/null
PGPASS=$(openssl rand -hex 16)
docker run -d --name "$DB" --network "$NET" -e POSTGRES_USER=bingo_piloto -e POSTGRES_PASSWORD="$PGPASS" \
  -e POSTGRES_DB=bingo_piloto postgres:16-alpine >/dev/null
sed -e "s#^DATABASE_URL=.*#DATABASE_URL=postgres://bingo_piloto:$PGPASS@$DB:5432/bingo_piloto?connect_timeout=3#" \
    -e "s#^SECRET_KEY=.*#SECRET_KEY=$(openssl rand -hex 32)#" \
    -e "s#^DJANGO_CSRF_TRUSTED_ORIGINS=.*#&,$BASE#" \
    deploy/piloto/bingo1-piloto.env.example > "$LOCAL/bingo1-piloto.env"   # porta local != 443: Origin leva :$PORT
ENV="$LOCAL/bingo1-piloto.env"
until docker exec "$DB" pg_isready -q -U bingo_piloto; do sleep 1; done
KORDAN=(-e KORDAN_RELEASE_VERSION="$VERSION" -e KORDAN_IMAGE_DIGEST="$DIGEST")

echo "== Perfil piloto sem DATABASE_URL"
out=$(docker run --rm -e KORDAN_RELEASE_VERSION="$VERSION" -e SECRET_KEY=x "$IMAGE" \
      python manage.py migrate --noinput --settings=core.settings_prod 2>&1 || true)
echo "$out" | grep -q "DATABASE_URL é obrigatório" && pass "recusa subir sem DATABASE_URL" || fail "não recusou: $out"

echo "== Migração (migrate_command do alvo, com KORDAN_SLOT vazio)"
docker run --rm --name "$WEB-migrate" --network "$NET" --env-file "$ENV" "${KORDAN[@]}" -e KORDAN_SLOT= \
  "$IMAGE" python manage.py migrate --noinput --settings=core.settings_prod >/dev/null
site=$(docker run --rm --network "$NET" --env-file "$ENV" "$IMAGE" python manage.py shell -v 0 --settings=core.settings_prod \
       -c "from django.contrib.sites.models import Site; print(Site.objects.get(id=1).domain, Site.objects.count())")
expect "Site do piloto" "$site" "$DOMAIN 1"
docker run --rm --network "$NET" --env-file "$ENV" "${KORDAN[@]}" "$IMAGE" \
  python manage.py migrate --noinput --settings=core.settings_prod >/dev/null
site=$(docker run --rm --network "$NET" --env-file "$ENV" "$IMAGE" python manage.py shell -v 0 --settings=core.settings_prod \
       -c "from django.contrib.sites.models import Site; print(Site.objects.get(id=1).domain, Site.objects.count())")
expect "Site após migrar de novo (idempotente)" "$site" "$DOMAIN 1"

echo "== Usuários de teste (uma vez, senha só neste comando)"
ADMIN_PASS=$(openssl rand -hex 12) PLAYER_PASS=$(openssl rand -hex 12)
docker run --rm --network "$NET" --env-file "$ENV" -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_PASSWORD="$ADMIN_PASS" -e DJANGO_SUPERUSER_EMAIL=admin@example.com \
  "$IMAGE" python manage.py createsuperuser --noinput --settings=core.settings_prod >/dev/null
docker run --rm --network "$NET" --env-file "$ENV" -e PLAYER_PASS="$PLAYER_PASS" "$IMAGE" \
  python manage.py shell -v 0 --settings=core.settings_prod \
  -c "import os; from django.contrib.auth.models import User; User.objects.create_user('jogador', password=os.environ['PLAYER_PASS'])"
pass "admin e jogador criados no PostgreSQL do piloto"

echo "== Slots pelo CMD da imagem"
for s in blue green; do
  docker run -d --name "$WEB-$s" --network "$NET" --env-file "$ENV" "${KORDAN[@]}" -e KORDAN_SLOT="$s" \
    --memory 512m --restart unless-stopped "$IMAGE" >/dev/null
done
cmd=$(docker inspect -f '{{join .Config.Cmd " "}}' "$WEB-blue")
echo "$cmd" | grep -q "0.0.0.0:8002.*DJANGO_SETTINGS_MODULE=core.settings_prod" && pass "CMD: $cmd" || fail "CMD inesperado: $cmd"

echo "== Nginx do piloto (HTTPS com certificado autoassinado)"
[ -f "$LOCAL/certs/privkey.pem" ] || openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=$DOMAIN" \
  -keyout "$LOCAL/certs/privkey.pem" -out "$LOCAL/certs/fullchain.pem" >/dev/null 2>&1
docker run -d --name "$NGINX" --network "$NET" --network-alias bingo1-piloto-nginx -p "127.0.0.1:$PORT:443" \
  -v "$HOST_DIR/deploy/piloto/nginx/bingo1-piloto.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$HOST_DIR/deploy/piloto/nginx/10-kordan-placeholder.sh:/docker-entrypoint.d/10-kordan-placeholder.sh:ro" \
  -v "$HOST_DIR/$LOCAL/upstreams:/etc/nginx/kordan-upstreams" \
  -v "$HOST_DIR/$LOCAL/certs:/etc/nginx/certs:ro" nginx:1.27-alpine >/dev/null
for _ in $(seq 30); do docker exec "$NGINX" curl -s -o /dev/null http://127.0.0.1/ 2>/dev/null && break; sleep 1; done
body=$(docker exec "$NGINX" curl -s http://bingo1-piloto-nginx/version)
echo "$body" | grep -q kordan_placeholder && pass "placeholder antes da primeira publicação" || fail "placeholder: $body"

echo "== Checagens do executor (direto nos slots, Host = slot_host_header)"
for s in blue green; do
  for _ in $(seq 60); do [ "$(slot_get $s /healthz)" = 200 ] && break; sleep 1; done
  expect "$s /healthz" "$(slot_get $s /healthz)" 200
  for path in / /static/css/index.css; do expect "$s smoke $path" "$(slot_get $s $path)" 200; done
  expect "$s /version" "$(slot_body $s /version)" "{\"version\": \"$VERSION\", \"commit\": \"$COMMIT\", \"slot\": \"$s\"}"
done
expect "Host desconhecido continua barrado" \
  "$(docker exec "$NGINX" curl -s -o /dev/null -w '%{http_code}' http://$WEB-blue:8002/)" 400
switch_to blue
expect "rota pública do executor (http://bingo1-piloto-nginx/version) → blue" \
  "$(docker exec "$NGINX" curl -s http://bingo1-piloto-nginx/version | sed 's/.*"slot": "\([a-z]*\)".*/\1/')" blue

echo "== Rota pública HTTPS"
expect "HTTP do domínio redireciona para HTTPS" \
  "$(docker exec "$NGINX" curl -s -o /dev/null -w '%{http_code}' -H "Host: $DOMAIN" http://127.0.0.1/)" 301
expect "GET /healthz sem redirecionar" "$(code "$BASE/healthz")" 200
expect "Cache-Control de /version" "$(web -D - -o /dev/null "$BASE/version" | tr -d '\r' | awk -F': ' 'tolower($1)=="cache-control"{print $2}')" no-store
expect "/version não cria sessão" "$(web -D - -o /dev/null "$BASE/version" | grep -ci set-cookie || true)" 0
expect "/cartela/ sem login continua exigindo login" "$(code "$BASE/cartela/")" 302
expect "estático pela rota pública" "$(code "$BASE/static/css/index.css")" 200

echo "== Partida: jogador salva cartela no blue"
JAR_P="$LOCAL/jogador.cookies" JAR_A="$LOCAL/admin.cookies"; rm -f "$JAR_P" "$JAR_A"
login() { # $1 jar, $2 usuário, $3 senha
  web -c "$1" -b "$1" -o /dev/null "$BASE/accounts/login/"
  local t; t=$(awk '$6=="csrftoken"{print $7}' "$1")
  web -c "$1" -b "$1" -o /dev/null -w '%{http_code} %{redirect_url}' -H "Origin: $BASE" -H "Referer: $BASE/accounts/login/" \
    --data-urlencode "csrfmiddlewaretoken=$t" --data-urlencode "login=$2" --data-urlencode "password=$3" "$BASE/accounts/login/"
}
expect "login do jogador por HTTPS" "$(login "$JAR_P" jogador "$PLAYER_PASS")" "302 $BASE/cartela/"
grep -q "#HttpOnly_$DOMAIN.*TRUE.*sessionid" "$JAR_P" && pass "cookie de sessão Secure e HttpOnly" || fail "cookie de sessão sem Secure"
TOKEN=$(awk '$6=="csrftoken"{print $7}' "$JAR_P")
expect "salvar cartela (15 itens)" "$(web -c "$JAR_P" -b "$JAR_P" -o /dev/null -w '%{http_code}' -H "X-CSRFToken: $TOKEN" \
  -H "Origin: $BASE" -H 'Content-Type: application/json' -d '{"items":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]}' "$BASE/cartela/salvar/")" 302

echo "== Troca para green (mesma sessão, mesmo banco)"
switch_to green
expect "rota pública → green" "$(web "$BASE/version" | sed 's/.*"slot": "\([a-z]*\)".*/\1/')" green
web -b "$JAR_P" "$BASE/confirmacao/" -o "$LOCAL/confirmacao.html" -w '%{http_code}' | grep -q 200 \
  && [ "$(grep -c card-item--selecionado "$LOCAL/confirmacao.html")" = 15 ] && pass "green mostra a cartela salva no blue, sem novo login" \
  || fail "sessão ou cartela não seguiram para o green"
expect "login do admin no green" "$(login "$JAR_A" admin "$ADMIN_PASS")" "302 $BASE/cartela/"
TOKEN=$(awk '$6=="csrftoken"{print $7}' "$JAR_A")
expect "apuração no green" "$(web -c "$JAR_A" -b "$JAR_A" -H "X-CSRFToken: $TOKEN" -H "Origin: $BASE" \
  -H 'Content-Type: application/json' -d '{"items":[1,2,3]}' "$BASE/cartela/conferir/")" '{"redirect": "/resultado/"}'
slot_body blue /resultado/ | grep -q '"jogador": "jogador", "total_iguais": 3' \
  && pass "blue lê o resultado apurado no green" || fail "blue não vê a apuração"
switch_to blue
[ "$(web -b "$JAR_P" "$BASE/confirmacao/" | grep -c card-item--selecionado)" = 15 ] && pass "volta ao blue mantém sessão e cartela" || fail "volta ao blue"

echo "== Banco indisponível"
docker stop "$DB" >/dev/null
for s in blue green; do
  expect "$s /healthz sem banco" "$(slot_get $s /healthz)" 503
  expect "$s corpo genérico" "$(slot_body $s /healthz)" unavailable
  expect "$s /version sem banco" "$(slot_get $s /version)" 200
done
docker start "$DB" >/dev/null; until docker exec "$DB" pg_isready -q -U bingo_piloto; do sleep 1; done
for _ in $(seq 20); do [ "$(slot_get blue /healthz)" = 200 ] && break; sleep 1; done
expect "blue /healthz com o banco de volta" "$(slot_get blue /healthz)" 200
expect "green /healthz com o banco de volta" "$(slot_get green /healthz)" 200

echo "== Memória dos slots"
docker stats --no-stream --format '  {{.Name}} {{.MemUsage}}' "$WEB-blue" "$WEB-green"
echo
echo "Tudo certo. Ambiente rodando em $BASE (certificado autoassinado; aponte $DOMAIN para 127.0.0.1)."
echo "Remover: deploy/piloto/validar_local.sh down"
