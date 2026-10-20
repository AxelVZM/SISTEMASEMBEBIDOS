#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sudo docker compose up -d --build --wait --wait-timeout 60 app
curl --fail --silent http://127.0.0.1:8010/api/health
printf '\nCódigo actualizado; la base permanece en el volumen de Docker.\n'
