#!/usr/bin/env bash
# Ejecutar SOLO desde la terminal web de AWS EC2 Instance Connect.
# Instala una nueva ruta estática para el experimento 3 sin reiniciar servicios existentes.
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$BASE/Panel_HTML"
DST="/var/www/esp32-experimento3"
SITE="/etc/nginx/sites-enabled/esp32-https"
SNIPPET="/etc/nginx/snippets/esp32-experimento3.conf"

if [[ ! -f "$SRC/index.html" || ! -f "$SRC/assets/escudo.png" ]]; then
  echo "ERROR: Faltan index.html o assets/escudo.png en $SRC"
  exit 1
fi
if [[ ! -e "$SITE" ]]; then
  echo "ERROR: No encuentro $SITE, vhost HTTPS esperado."
  echo "Sitios activos:"; ls -l /etc/nginx/sites-enabled/
  echo "Se detuvo sin modificar Nginx."
  exit 1
fi
CONFIG="$(readlink -f "$SITE")"
echo "Usando vhost HTTPS: $CONFIG"

sudo install -d -m 755 "$DST/assets" /etc/nginx/snippets
sudo install -m 644 "$SRC/index.html" "$DST/index.html"
sudo install -m 644 "$SRC/assets/escudo.png" "$DST/assets/escudo.png"

# Solo se crea una ruta nueva, no se cambian rutas /ESP32 existentes.
sudo tee "$SNIPPET" >/dev/null <<'NGINX'
# Experimento 3: Web Serial accede al puerto COM de la PC del visitante.
location = /ESP32/experimento3 {
    return 308 /ESP32/experimento3/;
}
location ^~ /ESP32/experimento3/ {
    alias /var/www/esp32-experimento3/;
    index index.html;
}
NGINX

BACKUP="${CONFIG}.bak-exp3-$(date +%Y%m%d-%H%M%S)"
sudo cp -a "$CONFIG" "$BACKUP"

# Insertar include únicamente dentro del server HTTPS, no en el de HTTP.
if ! sudo python3 - "$CONFIG" "$SNIPPET" <<'PYEDIT'
import re,sys
from pathlib import Path
p=Path(sys.argv[1]); snippet=sys.argv[2]
s=p.read_text(encoding='utf-8')
include='include '+snippet+';'
if include in s:
    print('Ruta ya incluida: manteniendo vhost sin cambios.')
    sys.exit(0)
if re.search(r'location\s+(?:=|\^~|~\*?|)\s*/ESP32/experimento3/?(?:\s|\{)', s):
    print('ERROR: Ya hay una ruta para experimento3 definida. Revisar el vhost; no duplico rutas.')
    sys.exit(3)
# Buscar bloques server { ... } respetando comillas, comentarios y llaves anidadas.
def closing(start):
    depth=0; quote=None; comment=False; escape=False
    for i in range(start,len(s)):
        c=s[i]
        if comment:
            if c=='\n': comment=False
            continue
        if escape: escape=False; continue
        if c=='\\' and quote: escape=True; continue
        if quote:
            if c==quote: quote=None
            continue
        if c=='#': comment=True; continue
        if c in ('"', "'"): quote=c; continue
        if c=='{': depth+=1
        elif c=='}':
            depth-=1
            if depth==0: return i
    raise ValueError('Bloque Nginx sin cierre')
blocks=[]
for m in re.finditer(r'\bserver\s*\{',s):
    start=s.index('{',m.start(),m.end());end=closing(start)
    block=s[start:end+1]
    if re.search(r'(?m)^\s*listen\s+[^;\n]*\b443\b',block):
        blocks.append((start,end,block))
if not blocks:
    print('ERROR: No se encontró un bloque server que escuche en 443.')
    sys.exit(4)
preferred=[b for b in blocks if '18.191.113.248' in b[2]]
if len(preferred)==1: selected=preferred[0]
elif len(blocks)==1: selected=blocks[0]
else:
    preferred=[b for b in blocks if '/ESP32/experimento2' in b[2]]
    if len(preferred)!=1:
        print('ERROR: Hay varios servidores HTTPS. No es seguro elegir uno automáticamente.')
        sys.exit(5)
    selected=preferred[0]
end=selected[1]
s=s[:end]+'    '+include+'\n'+s[end:]
p.write_text(s,encoding='utf-8')
print('Se agregó include en el vhost HTTPS.')
PYEDIT
then
  echo "ERROR: No se pudo editar la ruta. Restaurando copia de Nginx."
  sudo cp -a "$BACKUP" "$CONFIG"
  exit 1
fi

if ! sudo nginx -t; then
  echo "ERROR en Nginx: restaurando configuración anterior."
  sudo cp -a "$BACKUP" "$CONFIG"
  sudo nginx -t
  exit 1
fi
if ! sudo systemctl reload nginx; then
  echo "Error al recargar: restaurando configuración anterior."
  sudo cp -a "$BACKUP" "$CONFIG"
  sudo systemctl reload nginx || true
  exit 1
fi

echo
 echo "PUBLICACIÓN FINALIZADA EN LA INSTANCIA (verificar respuesta HTTP):"
curl -k -sS -o /dev/null -w 'Estado HTTP: %{http_code}\n' --resolve '18.191.113.248:443:127.0.0.1' 'https://18.191.113.248/ESP32/experimento3/' || true
echo 'URL: https://18.191.113.248/ESP32/experimento3/'
echo 'NOTA: El puerto COM se abre desde el navegador de la PC del usuario, no desde AWS.'
