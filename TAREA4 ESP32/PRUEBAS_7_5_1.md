# Verificación 7.5.1
- Compilación completa ESP32 clásico / Arduino-ESP32 3.3.2 / Huge APP correcta: 3.016.291 bytes de flash (95 %), 116.820 bytes de variables globales (35 %).
- Verificado en el ELF: btInUse es una definición fuerte (T), no la implementación débil (W) del core; devuelve true. Esto conserva memoria, no inicializa la radio.
- Verificada la configuración cfg.mode=ESP_BT_MODE_BLE en el código compilado; prueba C++ de control exige este modo.
- Prueba de control de modos C++ correcta: arranque Wi-Fi, BLE manual, parada asíncrona antes de recuperar Wi-Fi y rechazo de operaciones incompatibles.
- 19 pruebas API/puente correctas. Dos suites de interfaz correctas; añadidas comprobaciones de LAN dentro de Wi-Fi, configuración dentro de LAN y visualización del error BLE.
- Sin prueba física de radio, consumo de heap tras reservar Bluetooth ni descubrimiento en la LAN del usuario. No se afirma que el fallo LAN de su instalación esté resuelto sin conocer el estado/error.
- Los informes 7.5 anteriores son históricos. Esta corrección todavía requiere actualización de servidor y carga a la placa del usuario.
