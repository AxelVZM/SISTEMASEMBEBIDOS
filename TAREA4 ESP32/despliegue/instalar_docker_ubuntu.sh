#!/usr/bin/env bash
set -euo pipefail
# Solo instala Docker/Compose si faltan. No detiene Nginx/Apache/PM2 ni modifica sus sitios.
if command -v docker >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
    echo 'Docker Compose ya está disponible.'
    exit 0
fi
source /etc/os-release
if [[ "$ID" != ubuntu ]]; then
    echo 'Este instalador requiere Ubuntu 22.04/24.04. Instala Docker Compose para tu distribución y sigue README_EC2.md.' >&2
    exit 1
fi
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
printf '%s\n' "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
