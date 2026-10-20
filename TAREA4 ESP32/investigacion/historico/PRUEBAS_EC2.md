# Verificación de la integración EC2

Realizada el 20 de octubre de 2026.

## Ejecutado

- **16 pruebas** de API y puente: autenticación, archivos públicos permitidos, estado inicial sin sensor, recepción Wi-Fi/BLE y clasificación, expiración de estado, duplicados que no renuevan el estado, cambio de arranque, rechazo de sesiones mezcladas, protección ante dos puentes para el mismo ID, validación y límite de cuerpo, descarte de campos ajenos, orden temporal, historial, retención, persistencia SQLite, cola acotada y validación de URL.
- **HTTP real en localhost**: el método de envío del puente Python hizo POST al servidor, se persistió en SQLite, se consultó GET y se descargó la página. No se llamó a AWS.
- **Gunicorn real en localhost**: se inició el WSGI que usa el Dockerfile, con un worker y cuatro threads, y respondió correctamente `/api/health`.
- **DOM simulado** del panel y transporte: envío agrupado, token en cabecera y fuera del cuerpo, exclusión de configuración Wi-Fi, consulta remota, ausencia de bucle de reenvío de datos remotos, ausencia de estado actual al desconectar y bloqueo de funciones que requieren USB local. Las rutas de API son relativas para permitir `/esp32/`.
- Sintaxis Python, JavaScript y bash.
- **Firmware sin modificaciones**: los archivos `DetectorTiempoReal/` coinciden byte a byte con V7.2, compilado para ESP32 clásico, core 3.3.2 y Huge APP: 2 951 799 bytes (93 %), globales 103 876 bytes (31 %). No se necesita una compilación distinta para alojar la página en EC2.
- Se verificó sobre una copia local del repositorio que la adición se limita a `ESP32_EC2/`; TAREA1, TAREA2 y TAREA3 no se modificaron. No se hizo commit ni push.

## No ejecutado

No se ha usado un ESP32 físico, un COM real de Windows, tu instancia EC2, DNS público, un certificado real, Docker Compose, Caddy ni Nginx de tu servidor. No se midieron consumo, precisión de identificación, estabilidad prolongada ni latencia/pérdidas físicas. Las pruebas de DOM no son revisión visual en Chrome/Edge real.

El código está preparado y probado localmente en los aspectos anteriores; el despliegue necesita ejecutarse y verificarse en EC2 siguiendo README.md y README_EC2_HTTPS.md.

## Reproducir pruebas de servidor

Desde la raíz `ESP32_EC2`:

```bash
python3 -m pip install -r servidor/requirements.txt
python3 tests/test_ec2.py
python3 tests/test_ec2_http.py
```

La prueba del panel requiere Node y `happy-dom` disponible:

```bash
npm install --no-save happy-dom
node tests/test_ec2_ui.mjs
```

`test_ec2_http.py` abre un puerto efímero en localhost y lo cierra al terminar. Ninguna prueba incluye tokens de uso real.
