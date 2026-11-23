#!/usr/bin/env bash
set -e
cd /home/ubuntu/SISTEMASEMBEBIDOS
git pull --ff-only origin main
python3 -m venv .venv-exp2
.venv-exp2/bin/pip install -r "TAREA6 EXPERIMENTOS TINYML/experimento2/05_AWS/requirements.txt"
# Asegurar que service no apunte a un archivo de clave inexistente.
sudo sed -i '/^EnvironmentFile=/d' /etc/systemd/system/experimento2-tinyml.service
# Eliminar variable de token definida anteriormente en servicio, si existe (modo demo sin credenciales).
sudo sed -i '/^Environment=TINYML_INGEST_TOKEN=/d' /etc/systemd/system/experimento2-tinyml.service
sudo systemctl daemon-reload
sudo systemctl restart experimento2-tinyml
sudo systemctl is-active experimento2-tinyml
