# Experimento 2 en AWS

El modelo TinyML corre en ESP32-CAM. AWS solo recibe y grafica lecturas enviadas por el programa puente USB en Windows. La instancia EC2 NO tiene acceso al COM10 del PC.

## Git Bash, en la raíz del repositorio
```
cd "/c/Users/Usuario/Documents/Unsaac/SE/SISTEMASEMBEBIDOS"
mkdir -p "TAREA6 EXPERIMENTOS TINYML/experimento2"
# Copiar el contenido de este paquete a esa carpeta
 git add "TAREA6 EXPERIMENTOS TINYML/experimento2"
 git commit -m "Agregar experimento 2 TinyML y panel AWS"
 git push origin main
```

## EC2 Connect -> ubuntu
```
cd ~
if [ ! -d SISTEMASEMBEBIDOS/.git ]; then git clone https://github.com/AxelVZM/SISTEMASEMBEBIDOS.git; fi
cd SISTEMASEMBEBIDOS
git pull --ff-only
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip nginx
python3 -m venv .venv-exp2
.venv-exp2/bin/pip install -r "TAREA6 EXPERIMENTOS TINYML/experimento2/05_AWS/requirements.txt"
TOKEN=$(openssl rand -hex 32)
printf 'TINYML_INGEST_TOKEN=%s\n' "$TOKEN" | sudo tee /etc/experimento2-tinyml.env >/dev/null
sudo chmod 600 /etc/experimento2-tinyml.env
printf 'GUARDA ESTE TOKEN EN WINDOWS: %s\n' "$TOKEN"
sudo cp "TAREA6 EXPERIMENTOS TINYML/experimento2/05_AWS/experimento2-tinyml.service.example" /etc/systemd/system/experimento2-tinyml.service
sudo systemctl daemon-reload
sudo systemctl enable --now experimento2-tinyml
curl -s http://127.0.0.1:18762/health
```

**IMPORTANTE**: archivo systemd usa ruta `/home/ubuntu/SISTEMASEMBEBIDOS`. Si el usuario o ruta difieren, ajustar antes de habilitar servicio.

### Nginx
Primero encontrar el server HTTPS existente: `sudo nginx -T | grep -n -E 'listen 443|server_name|ESP32'`.
Editar el archivo REAL del bloque HTTPS (`sudo nano /etc/nginx/sites-available/...`), pegar el contenido de `05_AWS/nginx_experimento2.conf` DENTRO de `server {}` que atiende el 443. No reemplazar otros `location` existentes. `sudo nginx -t && sudo systemctl reload nginx`.

### Windows
Cerrar el monitor serie de Arduino, abrir `06_PUENTE_WINDOWS/iniciar_puente.cmd` y escribir el TOKEN mostrado en EC2.

**Atención HTTPS con IP**: si nginx no ofrece un certificado confiable para la IP `18.191.113.248`, Windows rechazará la conexión TLS. Lo adecuado es usar dominio y certificado valido. Para pruebas únicamente, ejecutar desde PowerShell: `.venv\Scripts\python.exe puente_usb_aws.py --port COM10 --token TOKEN --insecure` (arriesga interceptación del token; no usar en red no confiable). No poner el token en GitHub.

### Comprobaciones
`sudo systemctl status experimento2-tinyml --no-pager`, `sudo journalctl -u experimento2-tinyml -n 60 --no-pager`, `curl -I http://127.0.0.1:18762/`, `sudo nginx -t`.

### Seguridad
El endpoint de carga exige secreto aleatorio vía cabecera X-API-Key. Protege `/etc/experimento2-tinyml.env`. El tablero público muestra las mediciones. No publicar datos personales. No se requiere abrir puerto 18762 al exterior.

### Clasificacion
FRIO <12°C, TEMPLADO 12<=T<21°C, CALIENTE >=21°C. El firmware puede continuar con `MODO_CALIBRACION=true`; en ese caso la luz física sigue la referencia, NO la predicción neuronal.
