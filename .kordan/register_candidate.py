#!/usr/bin/env python3
"""Registra uma versão candidata na Central de Deploy da Kordan.

Usado pelo workflow do GitHub Actions e pela demonstração local. Só biblioteca padrão.

Autenticação, nesta ordem:
  1. --oidc: pede ao GitHub um token OIDC com a audiência da Central (exige `id-token: write`).
  2. Variável KORDAN_CI_TOKEN: token de CI emitido pela Central (fluxo local ou CI sem OIDC).

Se a Central estiver atrás do Cloudflare Access, defina também CF_ACCESS_CLIENT_ID e
CF_ACCESS_CLIENT_SECRET (token de serviço da política Service Auth da rota de CI). Esses
cabeçalhos só passam pelo Access; a Central continua exigindo o OIDC ou o token de CI.

Exemplos:
  register_candidate.py --status pending --version 1.4.0 --sequence 42 --commit <sha> --run-url <url>
  register_candidate.py --status passed  --version 1.4.0 --sequence 42 --commit <sha> --run-url <url> \
      --digest sha256:... --release-file kordan-release.json
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def github_oidc_token(audience):
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not request_token:
        raise SystemExit("OIDC indisponível: o job precisa de `permissions: id-token: write`.")
    request = urllib.request.Request(
        f"{url}&audience={audience}", headers={"Authorization": f"bearer {request_token}"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)["value"]


def read_release_file(path):
    """Marcação de release que exige manutenção, versionada no repositório da aplicação."""
    if not path or not os.path.exists(path):
        return False, ""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return bool(data.get("requires_maintenance", False)), str(data.get("reason", ""))


def access_headers():
    """Token de serviço do Cloudflare Access, quando configurado. Os dois valores ou nenhum."""
    client_id = os.environ.get("CF_ACCESS_CLIENT_ID", "")
    client_secret = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")
    if bool(client_id) != bool(client_secret):
        raise SystemExit("Defina CF_ACCESS_CLIENT_ID e CF_ACCESS_CLIENT_SECRET juntos, ou nenhum dos dois.")
    if not client_id:
        return {}
    return {"CF-Access-Client-Id": client_id, "CF-Access-Client-Secret": client_secret}


def post_candidate(central_url, token, payload, timeout=20):
    request = urllib.request.Request(
        central_url.rstrip("/") + "/api/v1/candidatas/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}", **access_headers()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"erro": body[:300]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("KORDAN_DEPLOY_URL"), help="URL da Central")
    parser.add_argument("--system", default=os.environ.get("KORDAN_SYSTEM"), required=False)
    parser.add_argument("--environment", default=os.environ.get("KORDAN_ENVIRONMENT"), required=False)
    parser.add_argument("--status", required=True, choices=["pending", "failed", "passed"])
    parser.add_argument("--version", required=True)
    parser.add_argument("--sequence", required=True, type=int)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--digest", default="")
    parser.add_argument("--release-file", default="kordan-release.json")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF", ""))
    parser.add_argument("--oidc", action="store_true", help="Autenticar com o OIDC do GitHub Actions")
    parser.add_argument("--audience", default=os.environ.get("KORDAN_OIDC_AUDIENCE", "kordan-deploy"))
    args = parser.parse_args(argv)

    for name in ("url", "system", "environment"):
        if not getattr(args, name):
            parser.error(f"--{name} é obrigatório (ou defina a variável de ambiente correspondente)")

    token = github_oidc_token(args.audience) if args.oidc else os.environ.get("KORDAN_CI_TOKEN")
    if not token:
        raise SystemExit("Sem credencial: use --oidc ou defina KORDAN_CI_TOKEN.")

    requires_maintenance, reason = read_release_file(args.release_file) if args.status == "passed" else (False, "")
    payload = {
        "system": args.system,
        "environment": args.environment,
        "repository": args.repository,
        "ref": args.ref,
        "version": args.version,
        "sequence": args.sequence,
        "commit_sha": args.commit,
        "ci_status": args.status,
        "image_digest": args.digest if args.status == "passed" else "",
        "ci_run_url": args.run_url,
        "requires_maintenance": requires_maintenance,
        "maintenance_reason": reason,
    }
    status, body = post_candidate(args.url, token, payload)
    print(f"Central respondeu {status}: {json.dumps(body, ensure_ascii=False)}")
    return 0 if status in (200, 201) else 1


if __name__ == "__main__":
    sys.exit(main())
