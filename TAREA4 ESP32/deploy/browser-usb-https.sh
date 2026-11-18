#!/usr/bin/env bash
# Run inside the project directory, on the existing Ubuntu instance.
set -euo pipefail
ip=${1:?Indica la IPv4 pública de EC2}
python3 -c 'import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])' "$ip"
site=/etc/nginx/sites-available/esp32-panel-web
root=/var/www/esp32-acme
hook=/etc/letsencrypt/renewal-hooks/deploy/esp32-nginx
test -f "$site"
test -f /etc/systemd/system/esp32-panel.service
test -x .venv/bin/python
.venv/bin/python -c 'from backend.main import browser_usb'
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$root/.well-known/acme-challenge"
apply_site() {
    cp "$site" "$tmp/previous"
    install -m 644 "$1" "$site"
    if ! nginx -t || ! systemctl reload nginx; then
        cp "$tmp/previous" "$site"
        nginx -t && systemctl reload nginx
        exit 1
    fi
}
cat > "$tmp/http" <<NGINX
server {
    listen 80;
    server_name ${ip};
    location ^~ /.well-known/acme-challenge/ { root ${root}; try_files \$uri =404; }
    location / { return 308 https://${ip}\$request_uri; }
}
NGINX
if [ ! -f "$site.before-browser-usb" ]; then cp -p "$site" "$site.before-browser-usb"; fi
# Keep a working TLS site available if this installer runs again.
if ! grep -Fq "root ${root};" "$site"; then apply_site "$tmp/http"; fi
echo 'En el grupo de seguridad de esta EC2: HTTP 80 desde 0.0.0.0/0 para validar y renovar el certificado; HTTPS 443 desde Mi IP para el panel. Conserva las reglas SSH.'
read -rp 'Después de guardar las reglas, pulsa Enter para continuar. '
if ! test -x /snap/bin/certbot; then snap install --classic certbot; fi
/snap/bin/certbot certonly --webroot -w "$root" --preferred-profile shortlived --ip-address "$ip" --cert-name "esp32-${ip}" --agree-tos --register-unsafely-without-email --non-interactive --keep-until-expiring
cp "$tmp/http" "$tmp/site"
cat >> "$tmp/site" <<NGINX
map \$http_upgrade \$esp_usb_upgrade {
    default upgrade;
    "" close;
}
map \$http_origin \$esp_usb_allowed {
    default 0;
    "" 1;
    "https://${ip}" 1;
}
server {
    listen 443 ssl;
    server_name ${ip};
    ssl_certificate /etc/letsencrypt/live/esp32-${ip}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/esp32-${ip}/privkey.pem;
    if (\$host != "${ip}") { return 403; }
    if (\$esp_usb_allowed = 0) { return 403; }
    proxy_http_version 1.1;
    proxy_set_header Host 127.0.0.1:8000;
    proxy_set_header Origin http://127.0.0.1:8000;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$esp_usb_upgrade;
    proxy_read_timeout 3600s;
    location = /ESP32/DetectorDispositivos { proxy_pass http://127.0.0.1:18000/; }
    location = /ESP32/DetectorDispositivos/ { return 308 /ESP32/DetectorDispositivos; }
    location /assets/ { proxy_pass http://127.0.0.1:18000; }
    location /api/ { proxy_pass http://127.0.0.1:18000; }
    location = /ws { proxy_pass http://127.0.0.1:18000; }
    location = /api/browser-usb {
        proxy_set_header Host 127.0.0.1:8000;
        proxy_set_header Origin \$http_origin;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$esp_usb_upgrade;
        proxy_pass http://127.0.0.1:18000;
    }
    location / { return 404; }
}
NGINX
apply_site "$tmp/site"
install -d "$(dirname "$hook")" /etc/systemd/system/esp32-panel.service.d
printf '#!/bin/sh\nnginx -t && systemctl reload nginx\n' > "$hook"
chmod 755 "$hook"
printf '[Service]\nEnvironment=DETECTOR_USB_ORIGIN=https://%s\n' "$ip" > /etc/systemd/system/esp32-panel.service.d/browser-usb.conf
systemctl daemon-reload
systemctl enable esp32-panel.service
systemctl restart esp32-panel.service
curl --retry 8 --retry-all-errors --retry-delay 1 -fsS --resolve "${ip}:443:127.0.0.1" "https://${ip}/ESP32/DetectorDispositivos" -o "$tmp/page"
grep -q 'id="usbConnect"' "$tmp/page"
echo "Panel preparado: https://${ip}/ESP32/DetectorDispositivos"
