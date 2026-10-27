# Actualizar a Órbita 7.3 · solo Wi-Fi

Esta entrega cambia la placa, la página y la API. No está instalada aún en tu EC2.

## 1. Descargar y preparar
Extrae el ZIP en Windows. La carpeta principal se llama ESP32_EC2.
Conserva una copia de la versión anterior. No reemplaces ni publiques tu archivo .env.

## 2. Actualizar GitHub y AWS
En tu repositorio SISTEMASEMBEBIDOS, dentro de TAREA4 ESP32, reemplaza:
- La carpeta web completa: index.html, ec2.js y wifi_catalog.json.
- servidor/app.py.
- La carpeta DetectorTiempoReal completa (para conservar también el firmware nuevo en GitHub).
- herramientas/puente_usb.py y herramientas/entrenar_huellas.py si utilizas estas herramientas.

Mantén los nombres de carpeta; no crees una carpeta ESP32_EC2 dentro de TAREA4 ESP32.
Los antiguos ble_core.h y bluetooth_companies.h pueden eliminarse: ya no se incluyen ni se utilizan.
Guarda los cambios en la rama que usa EC2. En la consola web de AWS ejecuta, uno por uno:

```bash
cd "$HOME/SISTEMASEMBEBIDOS/TAREA4 ESP32"
git pull --ff-only
bash despliegue/actualizar.sh
curl --fail https://18.191.113.248/esp32/api/health
```

Si git muestra conflicto, detente y comparte el error sin secretos. La respuesta de salud debe indicar firmware 7.3 (versión que admite la API; no prueba que ya cargaste la placa). No cambies Nginx, el certificado, el token ni el volumen de Docker. No ejecutes docker compose down -v.

## 3. Cargar el firmware nuevo
1. Cierra la pestaña que tiene conectado el USB y cualquier Monitor/Plotter Serie.
2. En Arduino IDE abre DetectorTiempoReal/DetectorTiempoReal.ino del ZIP. Mantén todos los .h de esa carpeta juntos.
3. Usa la configuración verificada: ESP32 clásico, placa ESP32 Dev Module, paquete esp32 de Espressif 3.3.2, partición Huge APP. Esta compilación no está verificada para ESP32-C3/S3 ni otras placas.
4. Selecciona el puerto USB del ESP32 y pulsa Subir. No actives borrado completo de flash: así se conservan los ajustes NVS y registros compatibles.
5. Cuando termine, cierra Arduino IDE.

## 4. Conectar y comprobar
Abre https://18.191.113.248/esp32/ en Chrome o Edge de Windows. Pulsa Ctrl+F5.
En Configuración y conexiones → Servidor EC2 introduce tu token, deja esp32-principal y guarda el enlace. Activa la publicación al servidor. Pulsa Conectar ESP32 y selecciona su USB.

Comprueba:
- Estado del sensor: firmware 7.3; radio Wi-Fi (o Red durante una subida opcional).
- No hay tarjeta, filtro ni ensayo Bluetooth.
- Explorador: columna Distancia estimada*. Sin telemetría reciente aparece Sin estimación actual.
- En una fila cliente, Detalles muestra Huella probe v1 y Probes observados si ese emisor envió solicitudes de sondeo capturadas. Las filas AP y dispositivos silenciosos pueden no tener huella.
- En otra pestaña puedes usar Ver sensor remoto para comprobar las huellas y distancias recibidas desde AWS.

## 5. Calibrar distancia
En Configuración y conexiones → Distancia estimada ajusta A y n. Los valores -45 dBm y 2,5 son iniciales orientativos, no una calibración real.
Coloca un equipo conocido a 1 m, fija orientación/canal/entorno y mide varios RSSI; usa la media como A. Mide después a varias distancias conocidas d>1 m y ajusta n; para un punto n=(A-RSSI)/(10 log10(d)). Reserva otras distancias para evaluar el error. Un ajuste para un emisor no calibra automáticamente todos los demás. La configuración es local a cada pestaña; no modifica la placa ni se comparte entre navegadores.

## 6. Mejorar marca/modelo con datos reales
Lee investigacion/METODO_Y_ENTRENAMIENTO.md. El catálogo entregado está vacío: no se inventan firmas ni se reporta un modelo entrenado. WPS/Wi-Fi Direct y pistas por nombres siguen funcionando, con su nivel de evidencia. «Sin determinar» es válido cuando no hay evidencia suficiente.
