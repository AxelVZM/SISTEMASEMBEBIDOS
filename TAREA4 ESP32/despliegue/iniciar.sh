#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
    echo 'Primero ejecuta: python3 herramientas/configurar_servidor.py' >&2
    exit 1
fi
sudo docker compose up -d --build --wait --wait-timeout 60 app
curl --fail --silent http://127.0.0.1:8010/api/health
printf '\nServidor iniciado en 127.0.0.1:8010. Usa túnel SSH o tu proxy HTTPS.\n'
