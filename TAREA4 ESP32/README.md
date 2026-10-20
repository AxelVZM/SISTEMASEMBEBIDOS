# ESP32_EC2 — Órbita: conteo y clasificación de emisiones

Proyecto completo para añadir a **https://github.com/AxelVZM/SISTEMASEMBEBIDOS** en una carpeta nueva `ESP32_EC2/`. Se conservan TAREA1, TAREA2 y TAREA3. Incluye firmware V7.2, panel USB, API y página para EC2, puente Windows y despliegue.

**La página y la API corren en EC2. El ESP32 está conectado por USB a tu PC Windows.** Un puente envía las mediciones al servidor. EC2 no accede directamente al USB de otro ordenador.

Elige un puente: **Python en Windows** (recomendado para dejarlo funcionando aunque cierres el navegador) o **Chrome/Edge en el PC conectado al ESP32**. No uses ambos sobre el mismo puerto COM a la vez.

## 1. Subir el proyecto a GitHub desde Windows

Instala Git si aún no lo tienes. En PowerShell:

```powershell
git clone https://github.com/AxelVZM/SISTEMASEMBEBIDOS.git
cd SISTEMASEMBEBIDOS
Expand-Archive "$env:USERPROFILE\Downloads\ESP32_EC2_Completo.zip" -DestinationPath . -Force
git add ESP32_EC2
git diff --cached --stat
git commit -m "Agregar contador ESP32 con pagina y API para EC2"
git push origin main
```

Si ya tienes una copia del repositorio, úsala en lugar de volver a clonarlo y actualízala antes de extraer. Ajusta la ruta del ZIP si no lo guardaste en Descargas. El ZIP contiene una sola carpeta `ESP32_EC2`; no reemplaza tus otras tareas. Git puede pedirte iniciar sesión en GitHub. No se ha hecho push desde esta entrega.

La configuración real `.env`, claves SSH y bases de datos están excluidas por `.gitignore`. No escribas contraseñas ni tokens reales en el código, ejemplos, commits o archivos README.

## 2. Iniciar el servidor en EC2

Se asume **Ubuntu 22.04/24.04**, coherente con la guía de EC2 de TAREA2. Entra por SSH y ejecuta:

```bash
cd ~
git clone https://github.com/AxelVZM/SISTEMASEMBEBIDOS.git
cd SISTEMASEMBEBIDOS/ESP32_EC2
python3 herramientas/configurar_servidor.py
bash despliegue/instalar_docker_ubuntu.sh
bash despliegue/iniciar.sh
```

Si el repositorio ya existe en EC2:

```bash
cd ~/SISTEMASEMBEBIDOS
git pull --ff-only origin main
cd ESP32_EC2
python3 herramientas/configurar_servidor.py
bash despliegue/instalar_docker_ubuntu.sh
bash despliegue/iniciar.sh
```

El configurador crea `.env` y muestra **tu token del servidor**. Guárdalo: lo introducirás en Windows y en la página. Si `.env` ya existe, se conserva; no se genera otra clave. La instalación requiere permisos `sudo` e Internet. No detiene Nginx, Apache, PM2 ni tus otras aplicaciones.

La API queda en **127.0.0.1:8010** de EC2. Ese puerto no se publica a Internet. El puerto interno del contenedor es 8000; no son el mismo puerto. Se eligió 8010 para no ocupar el 3000 usado por TAREA2 ni asumir disponible tu otro servicio 8000.

Comprobar:

```bash
curl http://127.0.0.1:8010/api/health
sudo docker compose ps
sudo docker compose logs --tail 60 app
```

Respuesta de salud prevista: `{"ok":true,"version":"ec2-1","firmware":"7.2"}` (el orden JSON puede variar). La salud del servidor **no significa que el ESP32 esté conectado**.

## 3. Probar YA sin comprar/configurar dominio

En el grupo de seguridad EC2 permite **SSH 22 desde tu IP**. Mantén la instancia accesible por su IP pública o Elastic IP. No abras 8010 a Internet.

Desde PowerShell en Windows abre un túnel, sustituyendo la ruta de tu PEM y la IP:

```powershell
ssh -i "C:\ruta\tu-clave.pem" -N -L 8010:127.0.0.1:8010 ubuntu@TU_IP_PUBLICA_EC2
```

**Deja esa ventana abierta.** En Chrome o Edge abre:

```text
http://localhost:8010
```

La página y la base siguen estando en EC2: localhost transporta la conexión a EC2 mediante SSH. Esta modalidad funciona sin dominio y permite Web Serial por tratarse de localhost. Si SSH usa otro usuario, reemplaza `ubuntu` por el de tu instancia. Si 8010 ya está ocupado en tu PC, usa `-L 8011:127.0.0.1:8010` y abre `http://localhost:8011`.

La dirección privada `10.144.188.158` no se asume accesible desde Internet: necesitarías conectividad privada/VPN o la IP pública correspondiente. No se ha intentado acceder a esa dirección.

## 4. Cargar el ESP32

1. Conecta el ESP32 físico a Windows por cable USB de datos.
2. Abre `DetectorTiempoReal/DetectorTiempoReal.ino` en Arduino IDE.
3. Instala **esp32 by Espressif Systems 3.3.2**. Para ESP32 clásico de 4 MB selecciona **ESP32 Dev Module**, **Flash Size 4MB**, **Huge APP (3MB No OTA/1MB SPIFFS)**, **PSRAM Disabled**, **Upload Speed 115200** y tu COM, por ejemplo COM6.
4. Verifica y carga. Si falla `Connecting`, mantén BOOT durante la conexión y suéltalo al comenzar la escritura.
5. Cierra el Monitor Serie antes de usar el puente. El firmware empieza a capturar automáticamente: no envías letras ni registras aparatos.

No hace falta recompilar si ya cargaste V7.2. El firmware entregado es idéntico al V7.2 compilado antes: la integración EC2 se añade en el PC y servidor.

**No necesitas ingresar la contraseña Wi-Fi en el ESP32 para este flujo USB.** El PC necesita conexión a Internet/EC2. Si guardaste una subida directa a Lambda en versiones anteriores, desactívala desde `PanelTiempoReal.html` antes de usar este flujo; esa función opcional es independiente de EC2 y puede pausar la escucha.

## 5. Ejecutar el puente Python en Windows

Desde tu copia local del repositorio:

```powershell
cd SISTEMASEMBEBIDOS\ESP32_EC2
py -m pip install -r herramientas\requirements.txt
py herramientas\puente_usb.py --port COM6 --server http://localhost:8010 --sensor esp32-principal
```

Introduce el **token generado en EC2** cuando se solicite: no se muestra ni queda en el comando. Si instalaste Python con el comando `python` en lugar de `py`, sustituye `py`. Cambia COM6 si tu puerto es otro.

Mantén encendido el ESP32 y **deja ejecutándose el puente**. La consola informa de recepción y reintenta si desconectas/reconectas USB. Si utilizas túnel SSH, también debe permanecer abierto.

En la página de EC2:

1. Abre **Servidor EC2 · conectar y consultar el sensor**.
2. Introduce el mismo token y el ID **esp32-principal**.
3. Pulsa **Ver sensor remoto**. **No pulses Conectar ESP32 mientras Python use el COM.**

La página actualiza automáticamente. Sin nuevas tramas de estado durante unos 5 segundos, la API indica ausencia de datos recientes y la vista deja de mostrar los conteos como actuales. Esto no demuestra que la placa esté apagada: también puede faltar el puente o la red.

Como alternativa al comando puedes hacer doble clic en `herramientas/iniciar_puente_windows.bat` tras instalar pyserial.

## 6. Alternativa sin Python: puente en Chrome/Edge

Con el puente Python y Monitor Serie cerrados, abre la página de EC2 por HTTPS o por el túnel localhost:

1. En **Servidor EC2** introduce token e ID y pulsa **Guardar enlace en esta sesión**.
2. Deja marcada **Enviar las observaciones de mi USB a este servidor**.
3. Pulsa **Conectar ESP32** y selecciona el COM.
4. Mantén esta pestaña abierta y activa; el navegador envía lotes cada ~0,5 s y puede ralentizar pestañas en segundo plano.

Otro navegador/equipo podrá consultar el mismo ID con **Ver sensor remoto** cuando el sitio sea accesible desde ese equipo. En modo remoto se desactivan órdenes USB, descarga del CSV de flash y ensayos; puedes consultar detalles, filtros, clasificación y exportar las filas recibidas.

Web Serial necesita un contexto seguro: **HTTPS o localhost**. Abrir una página en `http://IP_PUBLICA` no basta para conectar USB desde el navegador. El puente Python es independiente de Web Serial, pero también usa HTTPS salvo túneles localhost.

## 7. Publicar la página con HTTPS para verla desde otros equipos

Consulta `README_EC2_HTTPS.md`. Incluye:

- Un subdominio nuevo con Nginx + certificado, conservando el sitio de TAREA2.
- Una ubicación `/esp32/` dentro de tu sitio HTTPS existente.
- Caddy opcional únicamente si 80/443 están libres en esa instancia.

Con la URL pública, el puente se ejecuta así:

```powershell
py herramientas\puente_usb.py --port COM6 --server https://esp32.TU_DOMINIO --sensor esp32-principal
```

Si elegiste la ubicación dentro de un sitio existente:

```powershell
py herramientas\puente_usb.py --port COM6 --server https://TU_DOMINIO/esp32 --sensor esp32-principal
```

Ya no necesitas túnel SSH para el flujo normal. Entra a esa misma dirección desde el navegador, introduce el token y pulsa Ver sensor remoto. **EC2 no reemplaza al PC que tiene físicamente el USB: el puente debe seguir activo en ese PC.**

## Operación, datos y límites

- Procesamiento embebido: el ESP32 captura Wi-Fi de 2,4 GHz y BLE, cuenta por separado en ventanas de 60 s y clasifica por evidencia. No detecta cualquier aparato simplemente por estar encendido.
- Tipos: teléfono/celular, laptop, router, AP, cañón/proyector y otras categorías. Se distinguen anuncios no autenticados, palabras sugestivas, rol y desconocido. No se garantiza marca/modelo exactos ni se convierten MAC locales en MAC de fábrica.
- Los conteos son direcciones observadas, no personas ni equipos únicos. No se suman Wi-Fi y BLE.
- En el flujo recomendado USB, el envío se realiza en el PC: **no introduce las pausas de radio de la subida Wi-Fi del ESP32**. Se conserva la alternancia original 10 s Wi-Fi / 2 s BLE.
- La API conserva hasta 16 sensores, con 96 filas Wi-Fi y 32 BLE por sensor. Para varios puentes usa IDs distintos. Dos puentes con el mismo ID se bloquean temporalmente para evitar mezclar observaciones.
- SQLite persiste en un volumen Docker. Guarda el último estado/filas e historial de conteos cada 5 s, con retención de 7 días. La página carga hasta 4 h iniciales. **No se almacena todo el historial individual de tramas ni se respalda automáticamente el CSV de la placa.**
- El puente conserva solo las últimas filas pendientes, no una cola de eventos infinita. Tras un corte no reconstruye las observaciones perdidas. Los datos quedan obsoletos en la vista si falta estado reciente.
- Se transmiten MAC/nombres observados y clasificaciones; el token protege la consulta y envío. La página es pública pero los datos de API requieren el token. No se transmite la configuración/contraseña Wi-Fi. No es una plataforma multiusuario con permisos individuales.
- El token se guarda en sessionStorage de la pestaña. Los datos de la API no se cachean. No pongas el token en URLs ni en GitHub.

## Actualizar código y conservar datos

En EC2:

```bash
cd ~/SISTEMASEMBEBIDOS
git pull --ff-only origin main
cd ESP32_EC2
bash despliegue/actualizar.sh
```

No ejecutes `docker compose down -v` si deseas conservar el historial y certificados. Para reiniciar: `sudo docker compose restart app`. Para detener el servicio sin borrar volumen: `sudo docker compose stop app`.

## Verificaciones y alcance de esta entrega

Se probaron 16 casos de API/puente, una petición HTTP real en localhost de extremo a extremo y la integración de la página en DOM simulado: envío, token, clasificación, consulta remota, ausencia de bucle de reenvío y estado desconectado. Consulta `PRUEBAS_EC2.md`.

**No se ha desplegado en tu EC2, hecho push a GitHub ni probado con tu ESP32 físico.** Docker/Caddy/Nginx y certificados deben comprobarse en tu instancia. Los scripts y el ZIP están preparados para que los ejecutes con los pasos anteriores.
