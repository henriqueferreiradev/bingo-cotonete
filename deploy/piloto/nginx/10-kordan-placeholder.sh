#!/bin/sh
# Montado em /docker-entrypoint.d/ do nginx:alpine. Na primeira subida ainda não há upstream
# gerado pelo executor: cria um apontando para o placeholder, para o Nginx iniciar. Depois o
# arquivo pertence ao executor e nunca é sobrescrito aqui.
set -e
file=/etc/nginx/kordan-upstreams/bingo1-piloto.conf
if [ ! -f "$file" ]; then
  cat > "$file" <<'EOF'
# Gerado pelo executor da Kordan Deploy. Não edite manualmente.
# kordan-active-slot: none
upstream kordan_bingo1_piloto {
    server 127.0.0.1:8081;
    keepalive 16;
}
map $host $kordan_bingo1_piloto_slot { default "none"; }
EOF
  echo "kordan: upstream inicial criado em $file"
fi
