#!/usr/bin/env bash
# Ejecutar SOLAMENTE desde AWS EC2 Instance Connect (terminal WEB).
# Publica el panel estatico en el servidor HTTPS existente, sin tocar otros servicios.
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$BASE/Panel_HTML"
DST="/var/www/esp32-experimento3"
SNIPPET="/etc/nginx/snippets/esp32-experimento3.conf"

if [[ ! -f "$SRC/index.html" || ! -f "$SRC/assets/escudo.png" ]]; then
  echo "ERROR: faltan Panel_HTML/index.html o Panel_HTML/assets/escudo.png"
  exit 1
fi

# Detectar el vhost verdadero, no asumir que se llama esp32-https.
# Elegir de forma conservadora un servidor 443 con server_name del IP solicitado.
# Si hay varios candidatos igualmente probables, parar SIN modificar Nginx.
TARGET="$(sudo python3 - <<'PYSELECT'
import re, sys
from pathlib import Path

IP='18.191.113.248'

def end_brace(s, opening):
    depth=0; quote=''; escape=False; comment=False
    for i in range(opening,len(s)):
        c=s[i]
        if comment:
            if c=='\n': comment=False
            continue
        if escape:
            escape=False
            continue
        if quote:
            if c=='\\': escape=True
            elif c==quote: quote=''
            continue
        if c=='#': comment=True; continue
        if c in ('"', "'"): quote=c; continue
        if c=='{': depth+=1
        elif c=='}':
            depth-=1
            if depth==0: return i
    raise ValueError('llaves sin cerrar')

found=[]
for symlink in sorted(Path('/etc/nginx/sites-enabled').iterdir()):
    if not symlink.is_file(): continue
    p=symlink.resolve()
    s=p.read_text(encoding='utf-8')
    for match in re.finditer(r'\bserver\s*\{',s):
        op=s.find('{',match.start(),match.end())
        block=s[op:end_brace(s,op)+1]
        listens=re.findall(r'(?m)^\s*listen\s+([^;\n]+)\s*;',block)
        if not any(re.search(r'(?<!\d)443(?!\d)', x) for x in listens): continue
        name=re.findall(r'(?m)^\s*server_name\s+([^;\n]+);',block)
        names=' '.join(name).split()
        score=0
        if IP in names: score+=100
        if '/ESP32/experimento2' in block: score+=20
        if '/ESP32/' in block or '/ESP32 ' in block: score+=10
        found.append((score,p))
if not found:
    print('ERROR: no hay ningun server { listen 443 ... } en los sitios activos.',file=sys.stderr)
    sys.exit(2)
found.sort(key=lambda x:x[0],reverse=True)
if len(found)>1 and found[0][0]==found[1][0]:
    print('ERROR: hay varios servidores HTTPS igualmente probables; no selecciono uno sin confirmacion.',file=sys.stderr)
    for score,p in found: print(f'  {p} (prioridad {score})',file=sys.stderr)
    sys.exit(3)
print(found[0][1])
PYSELECT
)" || { echo "No se modifico Nginx."; exit 1; }

echo "Servidor HTTPS detectado: $TARGET"

# Preparar archivos y fragmento, sin borrar rutas existentes.
sudo install -d -m 755 "$DST/assets" /etc/nginx/snippets
sudo install -m 644 "$SRC/index.html" "$DST/index.html"
sudo install -m 644 "$SRC/assets/escudo.png" "$DST/assets/escudo.png"
sudo tee "$SNIPPET" > /dev/null <<'NGINX'
# El navegador abre el puerto COM local por Web Serial; la EC2 solo sirve HTML.
location = /ESP32/experimento3 {
    return 308 /ESP32/experimento3/;
}
location ^~ /ESP32/experimento3/ {
    alias /var/www/esp32-experimento3/;
    index index.html;
}
NGINX

BACKUP="${TARGET}.bak-exp3-$(date +%Y%m%d-%H%M%S)"
sudo cp -a "$TARGET" "$BACKUP"
if ! sudo python3 - "$TARGET" "$SNIPPET" <<'PYEDIT'
import re, sys
from pathlib import Path
p=Path(sys.argv[1]); snippet=sys.argv[2]
s=p.read_text(encoding='utf-8')
include='include '+snippet+';'

def end_brace(s,opening):
    depth=0; quote=''; escape=False; comment=False
    for i in range(opening,len(s)):
        c=s[i]
        if comment:
            if c=='\n':comment=False
            continue
        if escape: escape=False; continue
        if quote:
            if c=='\\':escape=True
            elif c==quote:quote=''
            continue
        if c=='#':comment=True;continue
        if c in ('"',"'"):quote=c;continue
        if c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return i
    raise ValueError('Bloque de Nginx sin cierre')

blocks=[]
for m in re.finditer(r'\bserver\s*\{',s):
    start=s.find('{',m.start(),m.end()); end=end_brace(s,start)
    block=s[start:end+1]
    if re.search(r'(?m)^\s*listen\s+[^;\n]*(?<!\d)443(?!\d)',block):
        blocks.append((start,end,block))
if not blocks:
    print('ERROR: en el archivo seleccionado no existe HTTPS en puerto 443');sys.exit(3)
if len(blocks)>1:
    matching=[b for b in blocks if re.search(r'(?m)^\s*server_name\s+[^;\n]*\b18\.191\.113\.248\b',b[2])]
    if len(matching)!=1:
        matching=[b for b in blocks if '/ESP32/experimento2' in b[2]]
    if len(matching)!=1:
        print('ERROR: varios bloques 443; no se puede elegir con seguridad');sys.exit(4)
    block=matching[0]
else: block=blocks[0]
start,end,body=block
if include in body:
    print('Ruta de experimento 3 ya instalada.');sys.exit(0)
if re.search(r'\blocation\s+(?:=\s*|\^~\s*)?/ESP32/experimento3(?:/|\s|\{)',body):
    print('ERROR: ya existe otro location para /ESP32/experimento3');sys.exit(5)
# Insertar antes del cierre de ESTE bloque HTTPS; no alterar otras rutas.
s=s[:end]+'    '+include+'\n'+s[end:]
p.write_text(s,encoding='utf-8')
print('Ruta agregada al servidor HTTPS.')
PYEDIT
then
  sudo cp -a "$BACKUP" "$TARGET"
  echo "ERROR de configuracion: restaurado $TARGET"
  exit 1
fi

if ! sudo nginx -t; then
  sudo cp -a "$BACKUP" "$TARGET"
  sudo nginx -t || true
  echo "ERROR nginx -t: configuracion anterior restaurada."
  exit 1
fi
if ! sudo systemctl reload nginx; then
  sudo cp -a "$BACKUP" "$TARGET"
  sudo systemctl reload nginx || true
  echo "ERROR reload: configuracion anterior restaurada."
  exit 1
fi

echo
printf 'Respuesta de EC2: '
curl -k -sS -o /dev/null -w '%{http_code}\n' --resolve '18.191.113.248:443:127.0.0.1' 'https://18.191.113.248/ESP32/experimento3/' || true
echo 'URL: https://18.191.113.248/ESP32/experimento3/'
echo 'El acceso USB usa Chrome/Edge en la PC del usuario, no EC2.'
