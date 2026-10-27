# Actualización y uso paso a paso

## Windows y GitHub
1. Extrae ESP32_EC2_v7_5_Identificacion.zip. La carpeta es ESP32_EC2.
2. En GitHub → SISTEMASEMBEBIDOS → TAREA4 ESP32 reemplaza:
   - web/index.html, web/ec2.js, web/modes.js y web/wifi_catalog.json.
   - servidor/app.py.
   - Todos los archivos de DetectorTiempoReal (incluidos los nuevos identity.h, ssdp_core.h, ssdp_runtime.h, ble_core.h, ble_models.h, ble_runtime.h, bluetooth_companies.h, lan_core.h y lan_runtime.h).
   - herramientas/puente_usb.py si usas el puente Python.
3. Guarda los cambios en la misma rama que usa EC2. No subas .env ni agregues una carpeta ESP32_EC2 dentro de TAREA4 ESP32.

## Consola web de AWS
Ejecuta uno por uno:

```bash
cd "$HOME/SISTEMASEMBEBIDOS/TAREA4 ESP32"
git pull --ff-only
bash despliegue/actualizar.sh
curl --fail https://18.191.113.248/esp32/api/health
```

Si git muestra un conflicto, detente y comparte el error sin secretos. La salud de la API debe anunciar firmware 7.5. Eso confirma el servidor, no que ya actualizaste la placa. Conserva .env y el volumen Docker. No necesitas cambiar Nginx, HTTPS ni tu token.

## Actualizar la placa
1. Cierra el panel que usa el USB y el Monitor/Plotter Serie.
2. Abre DetectorTiempoReal/DetectorTiempoReal.ino del ZIP en Arduino IDE; mantén todos sus .h juntos.
3. Para ESP32 clásico: ESP32 Dev Module, core Espressif 3.3.2, Partition Scheme Huge APP. Selecciona su puerto USB.
4. Deja desactivado Erase All Flash Before Sketch Upload para conservar ajustes y registros. Pulsa Subir.
5. Cuando termine, cierra Arduino IDE.

## Panel
1. Abre https://18.191.113.248/esp32/ en Chrome o Edge de Windows y pulsa Ctrl+F5.
2. En Configuración y conexiones → Servidor EC2, introduce tu token si está vacío; conserva esp32-principal, guarda y activa la publicación.
3. Pulsa Conectar ESP32 y elige el USB. El estado debe indicar firmware 7.5 y Wi-Fi activo.

### Bluetooth solo cuando tú lo pidas
Abre Bluetooth BLE y pulsa Activar detección BLE. El estado cambia a BLE seleccionado; la captura Wi-Fi queda pausada. Los resultados aparecen en su propia tabla con marca, modelo anunciado, identificador, fuente y señal.
Pulsa Desactivar BLE y volver a Wi-Fi para regresar. Abrir otra pestaña del panel NO desactiva BLE. Al reiniciar la placa vuelve siempre a Wi-Fi.
Para probar AirPods, algunos formatos solo se anuncian en determinadas condiciones (por ejemplo, al abrir el estuche); no se garantiza que un aparato anuncie permanentemente el formato compatible.

### Buscar en tu red local
1. Desactiva BLE.
2. Abre Red local → Configurar mi red. Se abre la configuración existente.
3. Escribe el SSID y contraseña de una red de 2,4 GHz a la que tenga acceso el ESP32; pulsa Guardar en ESP32. No es necesario activar la subida automática a Lambda.
4. Vuelve a Red local y pulsa Conectar y buscar servicios.
5. La asociación tiene un plazo de 10 segundos; mDNS y SSDP/UPnP pueden tardar aproximadamente otros 15–35 segundos, según los servicios y sus respuestas. Al terminar, la placa vuelve a Wi-Fi pasivo.
6. Revisa los servicios y los campos anunciados. Un celular/laptop que no publique estos servicios no aparecerá. Los resultados conservados llevan antigüedad; no implican que el equipo siga conectado.

La clave pasa por USB a NVS de la placa y no se incluye en la telemetría de descubrimiento. La consulta se hace desde el ESP32 en esa red, no desde AWS. La red del navegador puede ser distinta. Si el router aísla clientes, bloquea multicast o usa VLAN distintas, no se descubrirán todos los servicios.

## Comprobación física pendiente
Prueba primero activar/desactivar BLE varias veces y comprobar la reanudación Wi-Fi. Después usa un dispositivo compatible conocido y compara el modelo. Prueba también uno desconocido. Finalmente busca una impresora mDNS y un equipo UPnP conocidos en tu LAN. Comprueba que al terminar vuelve a Wi-Fi, y descarga el registro para verificar que incluye filas LAN. Si faltan datos, comparte los estados/error, nunca contraseñas ni tokens.

## Qué verificar al actualizar
- La API /api/health anuncia 7.5; la placa conectada también debe anunciar 7.5. Son actualizaciones independientes.
- Guarda la carpeta completa del firmware: los nuevos .h son necesarios. Actualizar solo el .ino no basta.
- Si aparece «Sketch too big», verifica Huge APP y que tu placa sea ESP32 clásico compatible. No uses estas instrucciones para ESP32-C3/S3 sin adaptar la placa y comprobar sus radios.
- No habilites «Erase All Flash» para una actualización normal. Descarga antes el registro si necesitas conservarlo como evidencia.
- El nuevo formato UPnP admite HTTP local con Content-Length y XML limitado a 8 KiB. Equipos con descripciones distintas pueden quedar sin identificar; no es una lista completa de clientes del router.
- Los cambios de este paquete son locales: todavía debes subirlos a tu repositorio, actualizar EC2 y cargar la placa. No se ha desplegado automáticamente.
