# Piloto do Bingo na Central de Deploy da Kordan (`bingo1-piloto`)

Ambiente isolado da instalação atual (`bingo.kordan.tech`, `docker compose` + `entrypoint.sh`),
com PostgreSQL próprio de dados fictícios, dois slots (blue/green) criados pelo executor e Nginx
próprio em contêiner. Nada aqui altera a instalação atual, o Nginx do host ou o DNS.

| Arquivo | Para quê |
| --- | --- |
| `core/ops.py`, `core/urls.py` | `GET /healthz` e `GET /version` |
| `core/settings_prod.py` | hosts e CSRF por variável (padrões = instalação atual), falha sem `DATABASE_URL` sob a Central, app do Discord por variável, erros 500 no log |
| `bingo/apps.py` | grava o domínio do Django Sites a cada `migrate` quando `DJANGO_SITE_DOMAIN` existe |
| `Dockerfile`, `.dockerignore` | CMD dos slots explícito, `APP_COMMIT` no build, contexto sem segredos e bancos |
| `.github/workflows/release.yml`, `.kordan/register_candidate.py` | testes → GHCR → registro da candidata por digest (OIDC) |
| `deploy/piloto/targets.bingo1-piloto.toml` | bloco do alvo para o `targets.toml` do executor |
| `deploy/piloto/bingo1-piloto.env.example` | modelo do `env_file` do alvo (sem segredos) |
| `deploy/piloto/nginx/` | Nginx do piloto e upstream inicial (placeholder) |
| `deploy/piloto/validar_local.sh` | validação local de ponta a ponta |

## Contrato com a Central (conferido no código de `kordan-deploy`)

- O executor injeta `KORDAN_SLOT`, `KORDAN_RELEASE_VERSION` e `KORDAN_IMAGE_DIGEST`, e **não**
  injeta o commit. O SHA vem do build (`--build-arg APP_COMMIT=${{ github.sha }}`), fica em
  `APP_COMMIT` na imagem e sai em `/version`. O workflow confere isso na imagem publicada.
- Slots sobem **sem comando**, pelo CMD da imagem: Gunicorn em `0.0.0.0:8002` com
  `--env DJANGO_SETTINGS_MODULE=core.settings_prod`. O Compose atual continua usando
  `command: /app/entrypoint.sh`.
- A migração é um contêiner separado com `migrate_command` (lista, sem shell) e
  `KORDAN_SLOT` vazio.
- Checagens diretas: `http://bingo1-piloto-web-<slot>:8002<caminho>` com `Host` igual a
  `slot_host_header`. O smoke exige 200 em cada `smoke_paths` e `/version` com `version` e `slot`
  exatamente iguais aos da operação.
- Rota pública: `public_url + /version`, aceita com `version` não vazio e o slot esperado, ou o
  JSON `kordan_placeholder` antes da primeira publicação. O `urllib` do executor segue
  redirecionamentos, por isso o bloco interno do Nginx não redireciona para HTTPS.
- `env_file`: `CHAVE=valor` por linha, **sem aspas** (o executor não remove aspas).

`/healthz`: `SELECT 1` a cada chamada; na primeira resposta saudável de cada processo confere que
não há migrações pendentes e guarda o resultado (sem carregar o grafo de novo). Banco fora ou
migração pendente → `503` com corpo `unavailable`, detalhe só no log. `/version`: JSON
`{"version", "commit", "slot"}` com `Cache-Control: no-store`; fora da Central, os campos valem
`"local"`. As duas rotas aceitam só GET/HEAD, não usam sessão nem login e não redirecionam.

## Estado da partida e troca de slot

| Onde | Backend | Na troca blue ↔ green |
| --- | --- | --- |
| Cartelas (`Cartela`) e apuração (`Apuracao`) | PostgreSQL do piloto | Mesmos dados nos dois slots |
| Sessões de login | `django.contrib.sessions` no banco | Continua logado (mesmo `SECRET_KEY` no `env_file`) |
| CSRF e mensagens | cookie + sessão | Continuam válidos |
| Cache | `LocMemCache` por processo, usado só pelos limites de tentativa do allauth | Contadores zeram; não afeta a partida |
| Tempo real | Não existe: sem WebSocket, SSE ou polling; páginas carregam uma vez e fazem POST | Nada a reconectar |
| Estáticos | Dentro da imagem (`collectstatic` no build), servidos pelo WhiteNoise | Cada slot serve os da própria versão |
| Arquivos enviados | Não existem | — |

Resultado: a troca não interrompe nem perde partidas em andamento. Uma requisição em voo durante o
reload do Nginx termina no slot antigo, que continua rodando. Ressalva: uma página aberta antes da
troca pode pedir um CSS ou JS que mudou de nome na versão nova. Isso só vale para quem altera
estáticos.

## 1. Testar localmente

Requer Docker e Git Bash (Windows) ou bash. Usa nomes `bingo1-piloto-local-*` e a porta
`127.0.0.1:18443`, sem tocar em outros contêineres.

```bash
deploy/piloto/validar_local.sh        # build, Postgres, migração, 2 slots, Nginx HTTPS e checagens
deploy/piloto/validar_local.sh down   # remove tudo
```

O script falha na primeira checagem que não passar. Ele cobre: contexto de build sem `.env`, bancos,
`venv` e `.git`; recusa sem `DATABASE_URL`; Site idempotente; CMD dos slots; placeholder; health,
smoke, `/version` e `Host` desconhecido barrado em cada slot; rota pública do executor;
redirecionamento HTTP → HTTPS; cookies `Secure`; login e cartela salvos no blue e lidos no green
sem novo login; apuração no green lida no blue; volta ao blue; `/healthz` 503 com banco parado e
200 quando ele volta.

Testes de unidade (perfil e banco dos slots, como no CI):

```bash
pip install -r requirements.txt   # o venv local está sem dj-database-url
docker run -d --name bingo-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16-alpine
DATABASE_URL=postgres://postgres:postgres@localhost:5432/postgres SECRET_KEY=x \
  python manage.py test --settings=core.settings_prod
```

## 2. Configurar o alvo na Central e na VPS

Valores do cadastro: repositório `henriqueferreiradev/bingo-cotonete`, ref `refs/heads/master`,
workflow `.github/workflows/release.yml`, sistema `bingo1`, ambiente `piloto`, chave do alvo
`bingo1-piloto`. O bloco gerado pelo painel usa a chave `bingo1-piloto`; confira no painel se o
identificador do sistema é mesmo `bingo1`, porque o workflow envia esse valor.

Na VPS, como quem administra o executor (tudo fora do git):

1. **Rede e banco do piloto**
   ```bash
   docker network create bingo1-piloto
   # /etc/kordan/bingo1-piloto-db.env (chmod 600): POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
   docker run -d --name bingo1-piloto-db --network bingo1-piloto --restart unless-stopped \
     --env-file /etc/kordan/bingo1-piloto-db.env -v bingo1-piloto-db:/var/lib/postgresql/data postgres:16-alpine
   ```
   `max_connections` do Postgres precisa caber os dois slots (2 workers cada, sem conexões
   persistentes) mais a migração.
2. **Variáveis do app**: copie `bingo1-piloto.env.example` para `/etc/kordan/bingo1-piloto.env`
   (chmod 600) e preencha `DATABASE_URL`, `SECRET_KEY`, domínio e Discord. O
   `DISCORD_CLIENT_ID` é obrigatório para a página inicial abrir: o banco do piloto não tem o
   SocialApp da produção. Use um app do Discord separado, ou um valor qualquer se o login pelo
   Discord não for testado.
3. **Nginx do piloto**: `nginx/bingo1-piloto.conf` como `conf.d/default.conf` de um
   `nginx:1.27-alpine` chamado `bingo1-piloto-nginx` na rede `bingo1-piloto`, com
   `nginx/10-kordan-placeholder.sh` em `/docker-entrypoint.d/`, o mesmo diretório ou volume de
   upstreams que o executor monta em `/srv/kordan/nginx-upstreams` montado em
   `/etc/nginx/kordan-upstreams`, e os certificados em `/etc/nginx/certs`.
   **[VPS]** O Nginx do host já ocupa 80/443. A entrada HTTPS do domínio do piloto (Cloudflare
   Tunnel apontando para `http://bingo1-piloto-nginx`, ou um `server` novo no Nginx do host) é
   uma decisão de infraestrutura que ainda falta tomar. Se o TLS terminar fora deste contêiner,
   siga o comentário do bloco 443 no `.conf`.
4. **Executor**: ligue o contêiner do executor à rede `bingo1-piloto` (no Compose da Central,
   acrescente a rede externa `bingo1-piloto` ao serviço `executor`). Ele chama os slots e o
   Nginx pelo nome.
5. **Pull do GHCR**: o executor puxa com as credenciais do Docker do próprio contêiner e não faz
   login. Deixe o pacote `ghcr.io/henriqueferreiradev/bingo-cotonete` público, ou monte no
   executor um `config.json` com um token `read:packages`.
6. **Alvo**: cole `targets.bingo1-piloto.toml` em `/etc/kordan/targets.toml`, troque o domínio
   de exemplo `bingo-piloto.kordan.tech` (aqui, no `.env` e no `.conf` do Nginx) e reinicie o
   executor. O painel passa de **Aguardando executor** para **Aguardando versão aprovada**.

Valores que dependem da VPS: `network`, `public_url`, `nginx_container`, `upstream_file`,
`env_file`, `slot_host_header`/domínio e a entrada TLS. `memory_limit = "512m"`: cada slot usou
cerca de 114 MiB localmente.

## 3. GitHub e primeira release

1. **Settings → Secrets and variables → Actions → Variables**: crie `KORDAN_DEPLOY_URL` (ex.:
   `https://deploy.kordan.tech`, sem `/api/...`). Enquanto ela não existir, o workflow pula todos
   os jobs. Pushes na master não registram nada.
2. Só se a rota `/api/v1/candidatas/` estiver atrás do Cloudflare Access: crie os **secrets**
   `CF_ACCESS_CLIENT_ID` e `CF_ACCESS_CLIENT_SECRET` com o token de serviço da política Service Auth
   (veja `docs/ACESSO-CLOUDFLARE.md` na Central). Não há outro segredo: a Central valida o token
   OIDC (`repository`, `ref`, `workflow_ref`).
3. Não existe outro workflow no repositório, e a instalação atual é atualizada à mão na VPS
   (`docker compose`). O push destas mudanças não altera a instalação atual. Antes de rebuildar
   a instalação atual com o novo `.dockerignore`, confirme que o `.env.production` dela tem
   `DATABASE_URL`: o `db.sqlite3` não entra mais na imagem.
4. **Primeira release**, com a Central na VPS pronta e a variável criada: **Actions → release
   → Run workflow** na `master` (ou um push na `master`). O workflow avisa a Central, roda os
   testes com PostgreSQL, publica `ghcr.io/henriqueferreiradev/bingo-cotonete:1.0.<run>` e registra
   o digest. No painel aparece **Atualização disponível**. Quem tem o papel *Publicação* clica
   em Atualizar, e o executor puxa por digest, migra, sobe o slot, faz o smoke, troca o Nginx e
   confere a rota pública.
5. **Usuário de teste, uma vez**, depois da primeira publicação (as tabelas já existem). Use a
   imagem do slot ativo:
   ```bash
   docker run --rm -it --network bingo1-piloto --env-file /etc/kordan/bingo1-piloto.env \
     ghcr.io/henriqueferreiradev/bingo-cotonete@sha256:<digest> \
     python manage.py createsuperuser --settings=core.settings_prod
   ```
   A senha é digitada no terminal e não fica na imagem nem no `env_file`. Jogadores de teste
   podem ser criados em `/admin/` e entram por `/accounts/login/`. Nada disso roda na subida dos
   slots.

## Pendências e riscos

- **VPS**: entrada TLS do domínio do piloto, DNS, executor na rede `bingo1-piloto`, acesso ao
  GHCR e `max_connections`. Nada disso foi testado fora da máquina local.
- **GitHub/GHCR**: o workflow passou no `actionlint` e o job de testes foi reproduzido localmente
  (mesmo comando e banco). OIDC, push no GHCR e registro na Central só são validados na primeira
  execução real. Recomendado: fixar as actions por SHA.
- `STATICFILES_STORAGE` em `settings_prod` é ignorado desde o Django 5.1, então o WhiteNoise serve
  os estáticos sem hash nem compressão (funciona, com cache curto). A troca para `STORAGES` muda
  a produção atual e ficou fora deste piloto.
- `.pyc` estão versionados no repositório (`__pycache__/`). Vale remover do índice em outra
  mudança.
