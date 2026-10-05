# Actualizar ANDES MAQANAKUY en AWS EC2

Esta versión está preparada para Ubuntu + Node.js + PM2 + Nginx.

## 1. Subir a GitHub

Reemplaza el contenido de `TAREA2` por el contenido de este paquete y desde tu PC:

```bash
git add TAREA2
git commit -m "TAREA2 Andes Maqanakuy Combat Plus v3"
git push origin main
```

## 2. Actualizar EC2

En tu instancia:

```bash
cd ~/SISTEMASEMBEBIDOS/TAREA2
git pull origin main
npm ci --omit=dev
pm2 restart andes-maqanakuy
pm2 save
```

Si `npm ci` no puede usarse por un lockfile modificado localmente:

```bash
npm install --omit=dev
pm2 restart andes-maqanakuy
```

## 3. Verificar versión

```bash
curl http://127.0.0.1:3000/healthz
```

Respuesta esperada:

```json
{"ok":true,"app":"andes-maqanakuy","version":"netplay-v5"}
```

Después:

```bash
pm2 status
sudo nginx -t
sudo systemctl restart nginx
curl -I http://127.0.0.1
```

## 4. Nginx

Si todavía no está instalado el sitio:

```bash
sudo cp nginx-andes-maqanakuy.conf /etc/nginx/sites-available/andes-maqanakuy
sudo ln -sf /etc/nginx/sites-available/andes-maqanakuy /etc/nginx/sites-enabled/andes-maqanakuy
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Apache debe permanecer detenido si Nginx usa el puerto 80:

```bash
sudo systemctl stop apache2
sudo systemctl disable apache2
```

## 5. Caché del navegador

Esta versión usa `?v=netplay-v5` en CSS/JS. Tras actualizar, abre la IP pública y usa una recarga fuerte (`Ctrl + Shift + R`) si el navegador conserva recursos antiguos.
