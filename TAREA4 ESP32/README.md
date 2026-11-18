# ESP32 Detector — publicación en EC2 sin cambiar la detección

Proyecto original completo + herramientas de despliegue. Firmware C/ESP-IDF, backend Python y frontend se conservan byte por byte. Consulta también `docs/README_ORIGINAL.md` para el funcionamiento original.

**Recomendación:** conserva el ESP32 por USB y FastAPI en tu PC Windows; utiliza EC2 con Nginx como acceso público mediante un túnel SSH inverso. Es la opción más simple para conservar el sistema y la detección actuales sin desarrollar un protocolo de ingesta. La PC debe permanecer encendida, conectada a Internet y con la sesión iniciada.

Flujo: navegador → EC2:8000 (Nginx) → EC2:127.0.0.1:18000 (SSH) → PC:127.0.0.1:8000 (FastAPI) → USB → ESP32. Las respuestas y WebSocket recorren la misma conexión. Las observaciones y clasificación permanecen en tu PC, no se almacenan en EC2.

**El ESP32 debe estar físicamente conectado por USB a la máquina que ejecuta FastAPI. Una EC2 normal no tiene acceso al USB de tu PC.** Docker, abrir puertos o cambiar COM6 por `/dev/ttyUSB0` en EC2 no resuelven esto. Los dispositivos detectados siguen siendo los cercanos al ESP32; el escaneo de red sigue correspondiendo a la red de la PC.

El backend escucha en `0.0.0.0:8000` con un solo proceso, sin `--reload` ni múltiples workers (el serial es exclusivo). Nginx escucha en `0.0.0.0:8000` en EC2; son máquinas diferentes. El frontend ya utiliza rutas relativas y `location.host`, por eso no requiere cambios.

## A) ESP32: cargar el binario y conectarlo

1. Extrae el ZIP. Abre PowerShell en `esp32-detector`. Instala Python 3.12 de 64 bits, Git y el cliente OpenSSH de Windows si faltan. Comprueba:

```powershell
py -3.12 --version
git --version
ssh -V
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pip install esptool==4.8.1
```

Se usa `requirements.txt` original. El antiguo `requirements-lock.txt` se conserva como evidencia histórica y no se utiliza en este despliegue.

2. Conecta el ESP32 original de 4 MB con un cable USB de datos. En Administrador de dispositivos → Puertos confirma su COM (predeterminado COM6). Cierra `idf.py monitor`, monitores Arduino y `INICIAR.bat` antes de cargar o arrancar el backend. Si ya tiene este firmware funcionando, no necesitas volver a cargarlo.

3. Carga el binario combinado, sin recompilar:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\flash-prebuilt.ps1 -Port COM6
```

El script verifica los SHA256 originales y escribe `firmware/prebuilt/esp32-detector.bin` en **0x0**. No escribas `application.bin` en 0x0. Si falla la conexión, mantén BOOT durante el inicio de la carga y suéltalo al comenzar la escritura. No es necesario borrar toda la flash.

4. Prueba el backend local:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Abre `http://127.0.0.1:8000`. Si el puerto es distinto de COM6, cámbialo en Configuración del panel y guarda. Comprueba `http://127.0.0.1:8000/api/health`: serial conectado, firmware respondiendo y escáneres alternándose. Un `status: ok` solo prueba backend/DB: revisa también `serial.connected`, `firmware.responding` y `scanners`. No todos los escáneres están activos simultáneamente. Conservar `ERROR_RECOVERY` indica un problema original de firmware/hardware, no de AWS.

Detén esta prueba con Ctrl+C antes de arrancar el supervisor. La adquisición empieza al arrancar FastAPI, aunque no haya navegador; abrir el panel muestra el estado en tiempo real. No se altera ese comportamiento original. No abras un puerto entrante 8000 en el firewall de Windows: el túnel usa loopback y sale por SSH.

## B) GitHub: subir el proyecto

1. Crea en GitHub un repositorio vacío llamado `esp32-detector`, sin README ni .gitignore automáticos. Sustituye `TU_USUARIO` por tu usuario real. Ejecuta en la raíz extraída:

```powershell
git init
git branch -M main
git add .
git status --short
git diff --cached --stat
git commit -m "Preparar despliegue EC2 con tunel SSH y Nginx"
git remote add origin https://github.com/TU_USUARIO/esp32-detector.git
git push -u origin main
```

Git pedirá autenticación mediante su gestor de credenciales. No pongas tokens dentro de la URL. Si no tienes identidad configurada, antes del commit usa `git config user.name "TU_NOMBRE"` y `git config user.email "TU_CORREO"`.

2. Revisa `git status` antes del commit: no deben aparecer `.venv`, claves `.pem`, `.env`, logs, `settings.json` ni la base de observaciones. **Sí deben aparecer `data/vendors.sqlite3` y `firmware/prebuilt/*.bin`**: son referencias y binarios necesarios. `.gitignore` los permite expresamente; excluirlos rompería identificación o carga del firmware. No se incluyen claves AWS, tokens ni credenciales en el paquete.

3. Para actualizar después:

```powershell
git add .
git commit -m "Actualizar configuracion de despliegue"
git push
```

Si eliges repositorio privado, en EC2 usa una clave de despliegue de solo lectura de GitHub (generada en EC2 y añadida en Settings → Deploy keys del repositorio). Después clona con `git@github.com:TU_USUARIO/esp32-detector.git`. Nunca copies tu clave privada al repositorio. Conserva tus datos originales fuera del control de versiones y respáldalos aparte.

## C) AWS EC2: instancia, red, servicio y acceso

### 1. Crear la instancia

En EC2 → Launch instance: Ubuntu Server **24.04 LTS x86_64**, tipo pequeño como `t3.micro`, disco gp3 de 16 GB, clave SSH descargada fuera del repo. Verifica el precio de tu región y elegibilidad antes de lanzar; no se presupone gratuidad. Usa una subred pública con ruta `0.0.0.0/0` a Internet Gateway y asignación de IPv4 pública. Anota la **IPv4 pública de EC2**. Una Elastic IP es opcional para conservar la dirección; también puede tener coste.

Hay dos IP distintas:

| Marcador | Significado |
|---|---|
| `IP_PUBLICA_DE_TU_PC` | IPv4 de salida de tu casa/universidad; AWS la muestra al elegir **My IP** |
| `IP_PUBLICA_EC2` | IPv4 pública de la instancia; es la dirección del panel |

Security Group: elimina reglas entrantes más amplias equivalentes y deja:

| Tipo | Protocolo | Puerto | Origen |
|---|---|---|---|
| SSH | TCP | 22 | `IP_PUBLICA_DE_TU_PC/32` |
| Custom TCP | TCP | 8000 | `IP_PUBLICA_DE_TU_PC/32` |

Mantén la salida predeterminada para descargar paquetes. **No abras 18000**: solo escucha en loopback. No abras 80/443 para este ejemplo. Si navegas desde otra red, autoriza la IP de esa red para 8000; conserva también la IP de la PC del ESP32 para 22. Si cambia tu IP de salida, actualiza las reglas. No uses la IP privada `192.168.x.x` como origen y no confundas `/32` con un puerto.

### 2. Conectar, clonar e instalar el servidor público

En PowerShell sustituye estas dos rutas/direcciones por las tuyas:

```powershell
$Ec2 = 'IP_PUBLICA_EC2'
$Key = "$env:USERPROFILE\Downloads\mi-clave.pem"
ssh -i "$Key" "ubuntu@$Ec2"
```

En la primera conexión verifica la huella SSH de la instancia antes de aceptarla (EC2 → Connect proporciona indicaciones de conexión y verificación). Esta conexión también guarda `known_hosts` para el supervisor. Si SSH informa permisos demasiado abiertos en la clave, desde PowerShell ajusta el archivo:

```powershell
icacls "$Key" /inheritance:r
icacls "$Key" /grant:r "$($env:USERNAME):(R)"
```

Ya dentro de **Ubuntu EC2**:

```bash
sudo apt-get update
sudo apt-get install -y git python3 curl
cd ~
git clone https://github.com/TU_USUARIO/esp32-detector.git
cd esp32-detector
sudo bash deploy/install-ec2.sh IP_PUBLICA_EC2
systemctl is-enabled nginx
systemctl is-active nginx
sudo nginx -t
```

El instalador instala Nginx y OpenSSH, valida la IPv4, crea `/etc/nginx/sites-available/esp32-detector` y habilita Nginx con systemd para reiniciarse con la instancia. En EC2 **no se instala ni ejecuta un segundo FastAPI**: en esta arquitectura las dependencias Python y el USB están en Windows. Clonar el código en EC2 proporciona la configuración del relay; ejecutar el backend allí sin serial no produciría detecciones.

OpenSSH estándar de Ubuntu admite el túnel inverso en loopback sin `GatewayPorts`. Si una política previa desactiva forwarding, revisa `sudo sshd -T | grep -E 'allowtcpforwarding|disableforwarding|gatewayports'`; se necesita forwarding remoto habilitado, `disableforwarding no` y puede permanecer `gatewayports no`. No habilites exposición pública del puerto del túnel.

Si UFW ya está activo (`sudo ufw status`), permite antes de continuar `sudo ufw allow from IP_PUBLICA_DE_TU_PC to any port 22 proto tcp` y lo mismo para 8000. No es necesario activar UFW para este ejemplo.

### 3. Iniciar backend + túnel desde Windows

Regresa a PowerShell de tu PC (no dentro de Ubuntu), raíz del proyecto. Usa la misma cuenta Windows que guardó la huella SSH:

```powershell
$Ec2 = 'IP_PUBLICA_EC2'
$Key = "$env:USERPROFILE\Downloads\mi-clave.pem"
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\run-windows.ps1 -Ec2Host $Ec2 -KeyFile "$Key"
```

El supervisor inicia FastAPI y ejecuta este túnel, reiniciando procesos que terminan:

```powershell
ssh -N -T -i "$Key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:18000:127.0.0.1:8000 "ubuntu@$Ec2"
```

Este comando es explicativo: **no lo ejecutes adicionalmente** si ya está el supervisor, pues el puerto estaría ocupado. No se requiere redirección de puertos en el router local y funciona detrás de NAT mientras la red permita SSH saliente. El script no envía contraseñas ni acepta huellas nuevas automáticamente. Si la clave necesita frase de paso, cárgala previamente en `ssh-agent` de tu cuenta o usa el modo manual con autenticación interactiva; `BatchMode` no puede pedirla.

### 4. Mantenerlo corriendo

EC2: Nginx ya queda bajo systemd. Comprueba o administra con:

```bash
sudo systemctl status nginx --no-pager
sudo systemctl restart nginx
sudo journalctl -u nginx -n 50 --no-pager
sudo tail -n 50 /var/log/nginx/error.log
```

Windows: detén el supervisor manual con Ctrl+C. Registra la tarea desde una **PowerShell como administrador de la misma cuenta Windows**:

```powershell
$Ec2 = 'IP_PUBLICA_EC2'
$Key = "$env:USERPROFILE\Downloads\mi-clave.pem"
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\register-windows-task.ps1 -Ec2Host $Ec2 -KeyFile "$Key"
Get-ScheduledTaskInfo -TaskName 'ESP32-Detector-AWS'
```

La tarea empieza ahora y al iniciar sesión, sin límite de duración; el supervisor reconecta SSH y reinicia FastAPI si terminan. **No es un servicio previo al inicio de sesión**: tras reiniciar debes entrar con esa cuenta. Puedes bloquear la pantalla, pero no cerrar sesión. Desactiva la suspensión con corriente en Configuración → Energía; si la PC se apaga o suspende no habrá datos en EC2. No ejecutes además `INICIAR.bat`. Para detener/eliminar, usa el Programador de tareas; al detener forzosamente, verifica que no queden procesos de este proyecto con el puerto 8000/COM abierto antes de reiniciar. Logs en `logs/backend.log`, `logs/tunnel.log` y `logs/supervisor.log`; revisa y limpia logs de procesos de larga duración según el espacio disponible.

### 5. Abrir y verificar

Abre **`http://IP_PUBLICA_EC2:8000`** desde la IP autorizada. No uses `0.0.0.0` en el navegador. Prueba desde PowerShell:

```powershell
curl.exe "http://IP_PUBLICA_EC2:8000/api/health"
```

En EC2:

```bash
ss -ltn | grep -E ':8000|:18000'
curl http://127.0.0.1:18000/api/health
```

El primer comando debe mostrar Nginx en `0.0.0.0:8000` y SSH en `127.0.0.1:18000`. En el navegador → F12 → Network → WS, `/ws` debe devolver **101** y nuevos mensajes cada ~2 segundos. Cambia una configuración reversible para comprobar también las peticiones de escritura. Nginx valida Host y Origin públicos y luego los adapta a localhost para respetar las restricciones originales del backend; no se relajan sus validaciones. El SG limita quién accede porque el panel original no tiene autenticación. HTTP sirve para la demostración restringida a tu IP; si lo compartes de forma más amplia, configura HTTPS y autenticación antes.

| Síntoma | Comprobación |
|---|---|
| Timeout al panel | IPv4 pública, SG 8000, UFW, ruta al Internet Gateway |
| 502 Bad Gateway | PC encendida, supervisor, `logs/tunnel.log`, puerto 18000 en EC2 |
| 403 | URL exacta `http://IP_PUBLICA_EC2:8000`; si cambió la IPv4 EC2, vuelve a ejecutar el instalador con la nueva IP |
| Panel sin datos / serial false | COM correcto, cable USB, monitor cerrado, solo un backend |
| Firmware en ERROR_RECOVERY | Diagnosticar ESP32 original; no es un fallo del proxy |
| WS no conecta | `/ws` 101, mismo origen público, `sudo nginx -t`, túnel activo |
| SSH Permission denied | usuario ubuntu, clave correspondiente, permisos/ssh-agent |

### Alternativa si realmente quieres FastAPI bajo systemd en Linux

Úsala en una máquina Linux física que tenga el ESP32 por USB, no en una EC2 corriente. El servicio incluido `deploy/esp32-detector.service` sirve para esa situación. Instala el repo en `/opt/esp32-detector`, Python 3.12 + venv, crea usuario `detector` con acceso a `dialout`, instala `backend/requirements.txt`, crea `/var/lib/esp32-detector/settings.json` con `{"port":"/dev/ttyUSB0"}` (o un identificador estable `/dev/serial/by-id/...`) y haz propietario a `detector`. Copia la unidad a `/etc/systemd/system/`, ejecuta `sudo systemctl daemon-reload` y `sudo systemctl enable --now esp32-detector`. Requiere proxy HTTP/WS equivalente para acceso público, ya que el backend conserva su restricción localhost.

Otra arquitectura es enviar eventos seriales desde la PC a una API autenticada en EC2 y ejecutar allí la clasificación. Requiere implementar y validar un agente de ingesta y un nuevo transporte; se deja como alternativa conceptual y no se incorpora porque excede la adaptación sin cambiar el flujo original. No se incluye USB remoto por Internet.

## Archivos y validación

Nuevos archivos de despliegue en `deploy/`; README y `.gitignore` preparados para GitHub. `docs/DEPLOY_VALIDATION.md` registra las pruebas reales del paquete y sus límites. No se han creado recursos AWS ni publicado un repositorio automáticamente.

Fuentes oficiales consultadas:
- AWS Security Groups: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html
- AWS parámetros de instancia: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-launch-parameters.html
- Nginx WebSocket: https://nginx.org/en/docs/http/websocket.html
- OpenSSH túnel remoto: https://man.openbsd.org/ssh
