#!/usr/bin/env bash
# Ubuntu 24.04. Public relay only; ESP32 + backend stay on Windows.
set -euo pipefail
PUBLIC_IP=${1:?Usage: sudo bash deploy/install-ec2.sh EC2_PUBLIC_IPV4}
python3 -c 'import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])' "$PUBLIC_IP"
apt-get update
apt-get install -y nginx openssh-server git curl
cat > /etc/nginx/sites-available/esp32-detector <<NGINX
# Reject foreign browser origins BEFORE mapping trusted requests to localhost.
map \$http_origin \$detector_origin_allowed {
    default 0;
    "" 1;
    "http://${PUBLIC_IP}:8000" 1;
}
map \$http_upgrade \$detector_connection {
    default upgrade;
    "" close;
}
server {
    listen 0.0.0.0:8000 default_server;
    server_name ${PUBLIC_IP};
    if (\$host != "${PUBLIC_IP}") { return 403; }
    if (\$detector_origin_allowed = 0) { return 403; }
    location / {
        proxy_pass http://127.0.0.1:18000;
        proxy_http_version 1.1;
        proxy_set_header Host 127.0.0.1:8000;
        proxy_set_header Origin http://127.0.0.1:8000;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$detector_connection;
        proxy_set_header X-Forwarded-For "";
        proxy_set_header X-Forwarded-Host "";
        proxy_set_header X-Forwarded-Proto "";
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/esp32-detector /etc/nginx/sites-enabled/esp32-detector
nginx -t
sshd -t
systemctl enable --now nginx ssh
systemctl reload nginx
printf 'Relay ready: http://%s:8000 (502 until the PC tunnel starts).\n' "$PUBLIC_IP"
