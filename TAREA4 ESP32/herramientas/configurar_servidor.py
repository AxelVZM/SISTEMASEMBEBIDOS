"""Genera .env local. No subas .env a GitHub."""
import argparse
import os
import re
import secrets
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--domain',default='',help='dominio apuntado a EC2; opcional si usarás túnel SSH')
a=p.parse_args()
if a.domain and not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',a.domain):p.error('Usa solo un dominio, sin https:// ni ruta')
root=Path(__file__).resolve().parents[1];target=root/'.env'
if target.exists():raise SystemExit('.env ya existe. Se conserva sin cambiar token ni configuración; edítalo para ajustar DOMAIN.')
token=secrets.token_hex(32)
fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write('ORBITA_API_TOKEN='+token+'\nDOMAIN='+a.domain+'\n')
print('Configuración creada en .env. Guarda este token para el puente y la página:')
print(token)
print('No publiques .env ni el token. Mantén .env para actualizar sin cambiar credenciales.')
