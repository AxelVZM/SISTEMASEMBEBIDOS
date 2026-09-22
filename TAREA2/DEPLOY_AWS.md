# Andes Maqanakuy — despliegue en AWS EC2

Este proyecto está preparado para ejecutarse detrás de Nginx con PM2 en una instancia Ubuntu de EC2.

## Puertos recomendados en el Security Group
- 22/TCP: SSH, idealmente restringido a tu IP.
- 80/TCP: HTTP público.
- 443/TCP: HTTPS público cuando agregues dominio/certificado.
- NO expongas 3000 públicamente: Nginx se conecta localmente a Node.js.

## Instalación inicial (Ubuntu)
```bash
sudo apt update
sudo apt install -y nginx git curl
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2
```

## Clonar y entrar a TAREA2
```bash
cd ~
git clone https://github.com/AxelVZM/SISTEMASEMBEBIDOS.git
cd SISTEMASEMBEBIDOS/TAREA2
npm ci --omit=dev
```

## Iniciar con PM2
```bash
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup
```
Ejecuta también el comando adicional que `pm2 startup` muestre en pantalla y luego vuelve a ejecutar `pm2 save`.

## Nginx
Desde `TAREA2`:
```bash
sudo cp nginx-andes-maqanakuy.conf /etc/nginx/sites-available/andes-maqanakuy
sudo ln -sf /etc/nginx/sites-available/andes-maqanakuy /etc/nginx/sites-enabled/andes-maqanakuy
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Luego abre en tu navegador:
`http://IP_PUBLICA_DE_TU_EC2`

## Actualizar después de subir cambios a GitHub
```bash
cd ~/SISTEMASEMBEBIDOS/TAREA2
git pull origin main
npm ci --omit=dev
pm2 restart andes-maqanakuy
```

## Comprobaciones
```bash
pm2 status
pm2 logs andes-maqanakuy
curl http://127.0.0.1:3000/healthz
sudo nginx -t
sudo systemctl status nginx
```

## HTTPS opcional con dominio
Cuando tu dominio apunte a la IP pública/Elastic IP:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com -d www.tudominio.com
```
