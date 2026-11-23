# Experimento 2 — USB directo desde el navegador

No requiere puente, instalacion local ni puerto COM fijo.

1. Reemplaza los archivos de `05_AWS` en tu repositorio (conserva los demás proyectos).
2. Sube con Git Bash: `git add "TAREA6 EXPERIMENTOS TINYML/experimento2/05_AWS" && git commit -m "USB Web Serial directo" && git push origin main`.
3. En la consola web EC2: `cd ~/SISTEMASEMBEBIDOS && git pull --ff-only origin main && sudo systemctl restart experimento2-tinyml`.
4. Abre https://18.191.113.248/ESP32/experimento2/ en Chrome/Edge de la PC conectada físicamente a la ESP32. Cierra el Monitor Serie y actualiza con Ctrl+Shift+R.
5. Pulsa Conectar ESP32-CAM, elige el adaptador USB CH340 actual y concede permiso. No necesita COM10 fijo.

### Correcciones
- Libera DTR/RTS de la ESP32-CAM-MB al abrir Web Serial.
- Admite el formato CAL de TinyML, TINYML anterior y DHT22 diagnóstico.
- Envía por fetch relativo `api/ingest` desde el navegador a AWS.
- Muestra conteo de bytes, líneas y lecturas válidas.
- No hace falta Python ni puente en Windows.

### Límites reales
- Chrome/Edge debe considerar el origen HTTPS seguro; si el certificado TLS de la IP es inválido, Web Serial podría estar bloqueado.
- Solo funciona en el navegador del PC con el USB conectado; no permite conectar a la ESP32 físicamente desde EC2.
- No se puede garantizar 0 bytes por HTML si la placa no está transmitiendo datos o se mantiene en reinicio.
- La API sin token admite escrituras de terceros; se recomienda protegerla más adelante.
- `model.h` fue suministrado por el usuario. Las etiquetas 12/21 deben corresponder al entrenamiento real.
