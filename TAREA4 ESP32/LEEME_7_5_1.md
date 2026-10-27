# Corrección 7.5.1

## Cambios
- BLE: se conserva la memoria del controlador antes de setup() mediante ble_reserve.cpp. En el binario 7.5 se enlazaba btInUse débil, que devuelve false; Arduino liberaba permanentemente la memoria BTDM durante initArduino().
- BLE: cfg.mode se fija a ESP_BT_MODE_BLE antes de esp_bt_controller_init. La configuración dual predeterminada no correspondía al posterior esp_bt_controller_enable(BLE).
- La reserva de memoria no enciende Bluetooth: el controlador se inicializa al pulsar Activar. Wi-Fi sigue siendo el modo inicial.
- Red local, tabla y configuración de SSID/clave pasan al apartado Wi-Fi. Se elimina la pestaña LAN independiente.
- Se muestran errores BLE, motivos de controles deshabilitados, IP al conectar LAN y estado Wi-Fi si vence el plazo de asociación.

## Alcance y diagnóstico
Las dos incompatibilidades BLE se comprobaron contra el código Arduino-ESP32 3.3.2 incluido en la compilación; no se ha probado una placa física. La prueba de control ahora exige explícitamente cfg.mode BLE. Las pruebas anteriores no simulaban la liberación de memoria antes de setup ni la incompatibilidad de modos; por eso no detectaron estos fallos.

Todavía no se conoce la causa de la falla LAN en la instalación del usuario. Esta corrección mejora su acceso y diagnóstico, pero no garantiza descubrir equipos silenciosos ni equipos que no publiquen mDNS/UPnP. Si falla, copia el mensaje exacto de Wi-Fi → Mi red local e indica si los botones estaban deshabilitados o la búsqueda terminó con cero resultados. No compartas contraseñas ni tokens.

Los controles requieren conexión USB local; Ver sensor remoto es solo lectura. El enlace del panel sigue siendo https://18.191.113.248/esp32/.

Actualiza GitHub, el servidor y la placa siguiendo ACTUALIZAR_7_5_1.md. Copia la carpeta completa DetectorTiempoReal, incluido ble_reserve.cpp. Usa el mismo ESP32 clásico, Arduino-ESP32 3.3.2 y Huge APP. Reinicia tras subir y comprueba firmware 7.5.1.
