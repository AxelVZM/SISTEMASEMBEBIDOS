# Experimento 3 — Publicación AWS EC2 (MISMA INSTANCIA)

Objetivo: https://18.191.113.248/ESP32/experimento3/

## Cambios de esta actualización
- Escudo `Panel_HTML/assets/escudo.png` pequeño a la derecha del encabezado.
- HTML original completo preservado, con Web Serial, TinyML, LEDs, gráficas y CSV.
- Un script que publica el HTML estático en Nginx sin crear instancias, puentes ni servidores nuevos.
- No se modifica el firmware, el modelo de Colab, los sensores ni las rutas anteriores.

## A. WINDOWS: extraer el ZIP y subir con Git Bash

Extrae la actualización en la carpeta que ya tienes:
`C:\Users\Usuario\Documents\Unsaac\SE\SISTEMASEMBEBIDOS\TAREA6 EXPERIMENTOS TINYML\experimento3`

Si ya existen `Panel_HTML/index.html`, reemplaza solo ese archivo.

Abre Git Bash y ejecuta:

```bash
cd "/c/Users/Usuario/Documents/Unsaac/SE/SISTEMASEMBEBIDOS"
git status --short
git add "TAREA6 EXPERIMENTOS TINYML/experimento3/Panel_HTML/index.html" "TAREA6 EXPERIMENTOS TINYML/experimento3/Panel_HTML/assets/escudo.png" "TAREA6 EXPERIMENTOS TINYML/experimento3/Deploy/deploy_ec2.sh"
git commit -m "Experimento 3: logo y publicacion AWS por HTTPS"
git push origin main
```

Git Bash NO se conecta a EC2, solo publica los archivos en GitHub.

## B. AWS: entrar SOLO por web

AWS Console > EC2 > Instances > seleccionar la instancia existente > Connect > EC2 Instance Connect > Connect.

En la terminal web:

```bash
cd /home/ubuntu/SISTEMASEMBEBIDOS
git pull --ff-only origin main
bash "TAREA6 EXPERIMENTOS TINYML/experimento3/Deploy/deploy_ec2.sh"
```

El script agrega solo la ruta del experimento 3 al Nginx HTTPS activo (`esp32-https`).
Publica los archivos en `/var/www/esp32-experimento3/` y valida `nginx -t` antes de recargar.
Conserva un respaldo del vhost, y lo restaura si falla la validación.

## C. Usar la página

Desde la misma PC donde está conectada tu ESP32-CAM-MB por USB, abre en Chrome o Edge:
`https://18.191.113.248/ESP32/experimento3/`

Cierra el Monitor Serie de Arduino. Pulsa **Conectar ESP32-CAM (elegir COM)** y autoriza el puerto correcto.
Las lecturas llegan continuamente por Web Serial al navegador a 115200 baudios.
AWS solo entrega la página: el puerto COM y el CSV descargado siguen siendo LOCALES en la computadora.
Si abres la URL en otra PC o teléfono sin ese USB no podrás ver mediciones en vivo con esta arquitectura.

**HTTPS**: para Web Serial, el navegador debe reconocer el contexto como seguro. Si advierte certificado no confiable, hay que configurar un certificado confiable para el sitio; saltarse una advertencia no garantiza que Web Serial esté habilitado.

## Actualizaciones siguientes

Vuelve a hacer `git add` / `git commit` / `git push` desde Git Bash y, en EC2 web:

```bash
cd /home/ubuntu/SISTEMASEMBEBIDOS
git pull --ff-only origin main
bash "TAREA6 EXPERIMENTOS TINYML/experimento3/Deploy/deploy_ec2.sh"
```

La ruta de experimentos previos no se toca.
