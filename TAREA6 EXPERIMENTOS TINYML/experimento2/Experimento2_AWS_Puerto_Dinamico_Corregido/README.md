# CORRECCIÓN: CONEXIÓN ESP32-CAM -> AWS

## Diagnóstico confirmado
- AWS /health y /api/state responden correctamente. `records:0` significa que todavía no llegaron datos.
- El panel Web Serial solo puede abrir el USB del equipo Windows que navega, nunca el USB desde EC2.
- Se repara el estado infinito "Conectando", se distingue selección de puerto, apertura, lectura y envío.
- El puente anterior pedía token obligatoriamente. Se corrige para servidores sin token.

## Subir a GitHub
Reemplaza solo 05_AWS/index.html y 06_PUENTE_WINDOWS/puente_usb_aws.py e iniciar_puente.cmd del proyecto. Ejecuta git add, git commit y git push.

## EC2 consola web
cd /home/ubuntu/SISTEMASEMBEBIDOS
git pull origin main
sudo systemctl restart experimento2-tinyml
curl -s http://127.0.0.1:18762/health

## Opción 1: Web Serial en Chrome/Edge
Desde PC con ESP32-CAM conectada por USB; cerrar Arduino Monitor Serie; entrar a https://18.191.113.248/ESP32/experimento2/; Ctrl+F5; pulsar Conectar; elegir CH340.
Si el HTTPS tiene certificado autofirmado/no válido, el navegador puede bloquear Web Serial; no es solucionable por HTML.

## Opción 2: puente local (alternativa fiable si Web Serial falla)
Desde Windows, doble clic en 06_PUENTE_WINDOWS/iniciar_puente.cmd. Cierra Arduino Monitor Serie y NO pulses Conectar USB en el panel al mismo tiempo. El navegador solo mostrará mediciones en AWS.
El puente usa validación TLS: si el certificado de la IP es incorrecto, verás CERTIFICATE_VERIFY_FAILED. Corrige el certificado para una solución segura. Para diagnóstico aislado únicamente, se admite `python puente_usb_aws.py --port COM10 --insecure`; esto DESACTIVA seguridad TLS y no se recomienda para operación.

## Qué NO se modifica
- No modificar firmware ni model.h ni dataset: son independientes de la conexión serial web.
- No modificar Nginx si /api/state responde.

## Seguridad
El servidor sin token y con una comprobación Origin no tiene autenticación robusta. No mantener la recepción pública de datos sin autenticación si el servicio estará expuesto regularmente.
