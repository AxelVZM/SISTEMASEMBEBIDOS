# Experimento 2 — paquete integrado con el modelo proporcionado

Incluye el `model.h` cargado por el usuario, sin reentrenarlo ni sustituirlo. Se mantienen GPIO13 DHT22, GPIO14 LED azul, GPIO15 verde, GPIO2 rojo. Clases de referencia: <12 FRIO; [12,21) TEMPLADO; >=21 CALIENTE.

## 1. ESP32-CAM (Arduino IDE)
Abrir `03_ESP32_CAM/TinyML_Calibrado/TinyML_Calibrado.ino`, con `model.h` en la misma carpeta. Instalar `ArduTFLite` y `DHT sensor library` + `Adafruit Unified Sensor` y cargar en AI Thinker ESP32-CAM. El programa publica `BOOT`, `READY` y `CAL,...` a 115200. Las predicciones salen del modelo, salvo fallo de inferencia (fallback a umbral indicado en CSV).

## 2. Windows (USB CH340)
Ejecutar `06_PUENTE_WINDOWS/iniciar_puente.cmd` con la ESP32-CAM conectada. Detecta automáticamente COM, se reconecta y envía datos a AWS. Cerrar Monitor Serie Arduino y NO abrir el puerto USB desde la página web simultáneamente. El panel AWS es solo visor y funciona desde cualquier equipo.

Si AWS utiliza un certificado autofirmado de IP, Windows rechazará HTTPS. Solución permanente: certificado válido. Para demo controlada solamente, desde PowerShell, en la carpeta 06_PUENTE_WINDOWS y con el entorno creado: `.venv\Scripts\python.exe puente_usb_aws.py --port auto --insecure`. Este modo **no valida la identidad del servidor**; no usar en redes no confiables.

## 3. AWS EC2 — consola web solamente
Después de subir esta carpeta a GitHub, en EC2 ejecutar:

```bash
cd /home/ubuntu/SISTEMASEMBEBIDOS
git pull --ff-only origin main
python3 -m venv .venv-exp2
.venv-exp2/bin/pip install -r "TAREA6 EXPERIMENTOS TINYML/experimento2/05_AWS/requirements.txt"
sudo sed -i '/^EnvironmentFile=/d; /^Environment=TINYML_INGEST_TOKEN=/d' /etc/systemd/system/experimento2-tinyml.service
sudo systemctl daemon-reload
sudo systemctl restart experimento2-tinyml
```

No tocar Nginx: ya sirve `/ESP32/experimento2/`. El servidor recibe datos sin token en modo demostracion, por decisión del usuario. Este endpoint es públicamente escribible: no usar datos personales, y protegerlo antes de un despliegue permanente.

## Limitaciones
La compilación sobre placa y la conexión real no pueden confirmarse desde este entorno. Tampoco se ha podido corroborar que el modelo adjunto se haya entrenado con etiquetas 12/21; el firmware informa tanto la salida de red como la referencia. El modelo se conserva idéntico al recibido.
