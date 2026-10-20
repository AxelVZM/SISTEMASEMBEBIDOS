# Página pública con HTTPS en EC2

El método rápido con túnel SSH está en README.md y funciona sin dominio. Para una página accesible desde móviles u otros PC, utiliza un dominio/subdominio que controles.

## Opción recomendada: subdominio nuevo y Nginx existente

Tu repositorio contiene una guía de Nginx para TAREA2. Este procedimiento añade otro sitio; no reemplaza el sitio actual ni detiene PM2.

1. Crea un registro DNS **A** como `esp32.tu-dominio.com` hacia la IP pública o Elastic IP de EC2. Si utilizas AAAA, su IPv6 también debe apuntar correctamente; no añadas una IPv6 que no esté configurada.
2. En el grupo de seguridad permite TCP **80 y 443** desde los clientes que accederán al sitio. Conserva SSH 22 limitado a tu IP. **No publiques 8010**: Nginx se conecta por loopback.
3. Asegúrate de que `bash despliegue/iniciar.sh` haya iniciado la API. En EC2, dentro de `ESP32_EC2`, reemplaza el ejemplo de dominio y ejecuta:

```bash
ORBITA_DOMINIO=esp32.tu-dominio.com
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
sed "s/DOMINIO_ESP32/$ORBITA_DOMINIO/g" despliegue/nginx-esp32-dominio.conf | sudo tee /etc/nginx/sites-available/orbita-esp32 >/dev/null
sudo ln -s /etc/nginx/sites-available/orbita-esp32 /etc/nginx/sites-enabled/orbita-esp32
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d "$ORBITA_DOMINIO"
```

Si el enlace del sitio ya existe, no necesitas repetir `ln -s`. Elige un subdominio nuevo; no sustituyas un dominio que ya aloje otra aplicación. Certbot necesita que DNS y los puertos permitan completar el desafío del certificado.

4. Abre `https://esp32.tu-dominio.com`, introduce el token y usa el ID configurado en tu puente Windows.

El archivo de configuración propuesto es un sitio HTTP inicial; Certbot agrega HTTPS. No se presenta ese archivo HTTP como un certificado ya instalado.

## Si prefieres /esp32/ dentro de tu sitio HTTPS actual

Pega las dos ubicaciones de `despliegue/nginx-esp32-location.conf` **dentro del bloque server HTTPS** de tu sitio actual. Conserva sus otras ubicaciones. Después:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

La página será `https://TU_DOMINIO/esp32/` y la API `https://TU_DOMINIO/esp32/api/...`. La página usa rutas relativas y el proxy quita el prefijo. En el puente usa `--server https://TU_DOMINIO/esp32`, sin añadir `/api`.

Si tu sitio actual solo tiene HTTP, configura antes su certificado. Para el botón USB del navegador no basta abrir una IP pública mediante HTTP; como alternativa usa el túnel localhost y el puente Python.

## Caddy opcional en una instancia sin Nginx/Apache ocupando 80/443

No ejecutes esta opción en paralelo con el Nginx que ya usa esos puertos. Establece `DOMAIN=esp32.tu-dominio.com` en `.env`, apunta DNS y permite 80/443. Ejecuta:

```bash
sudo docker compose --profile https up -d --build
```

Caddy intentará emitir y renovar el certificado automáticamente. Revisa:

```bash
sudo docker compose logs --tail 80 https
```

Se conservan certificados en volúmenes. No se ha realizado emisión real en esta entrega. El método Nginx anterior permite compartir la misma instancia con TAREA2.
