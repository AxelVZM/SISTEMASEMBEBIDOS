# Prueba con el ESP32 físico — PENDIENTE DE PRUEBA FÍSICA

Esta guía no constituye un resultado de hardware. En el entorno de desarrollo no se ha accedido al ESP32 del usuario ni a su COM6. Utiliza equipos propios o autorizados.

1. Cierra el backend y cualquier monitor serial. Carga `firmware/prebuilt/esp32-detector.bin` desde `0x0`, o compila y carga desde una terminal ESP-IDF 5.4.2 con `idf.py -p COM6 flash monitor`.
2. En el monitor a 115200 comprueba JSON Lines con `v:2`, versión `2.0.0`, estados `WIFI_SCAN`, `BLE_SCAN`, `BT_CLASSIC_SCAN`, `PROCESS_EVENTS`, `IDLE` y heartbeats. Guarda el log como evidencia de esta prueba. El firmware debe confirmar inicio BLE/Classic mediante callbacks antes de declarar esos escáneres activos.
3. Sal del monitor con Ctrl+] para liberar COM6. Ejecuta INICIAR.bat; verifica en el panel cada componente, la fase y la confirmación ACK de configuración. «En vivo» es el enlace WebSocket, no prueba por sí solo captura de radio.
4. Desconecta USB. El servidor y el panel deben continuar; serial y firmware pasarán a desconectado/sin respuesta. Reconecta y comprueba la recuperación en varios segundos. Anota si el convertidor USB provoca un nuevo arranque.
5. Aplica Rápido, Equilibrado y Exhaustivo. Espera el siguiente ciclo y el ACK. Compara crecimiento de tiempos acumulados, cambios de fase y duración real. No se garantiza descubrir todos los equipos con Exhaustivo.
6. Prueba un Android: Wi-Fi 2.4 GHz activado y, por separado, algún anuncio BLE conocido o modo descubrible Classic. Los datos móviles por sí solos no son captados: este ESP32 no es receptor celular. Un teléfono puede no emitir un anuncio visible ni responder a inquiry.
7. Prueba una laptop: actividad de red 2.4 GHz autorizada, Bluetooth activo y, si procede, modo descubrible. No presupongas que Wi-Fi activo implica transmisión continua.
8. Prueba un router propio 2.4 GHz en un canal del 1 al 11; confirma MAC transmisora, canal y rol «Punto de acceso». No lo conectes obligatoriamente a Internet.
9. Prueba un dispositivo Bluetooth propio, por ejemplo audífonos en modo descubrimiento o un emisor BLE. Anota si aparecen BLE, Classic o ambos; son identidades independientes, no se fusionan.
10. Para RSSI selecciona un emisor estable, confirma autorización y captura al menos cinco observaciones aceptadas a 1/3/5/10 m. Si no reúne lecturas, aumenta la ventana, reduce deduplicación o usa un dispositivo que anuncie; no inventes valores. Repite con obstáculos y orientación diferente para comprobar incertidumbre.
11. Mantén el sistema durante 30–60 minutos. Registra heap mínimo, eventos de cola descartados, máximo observado de cola, reinicios y motivo. Comprueba que un entorno denso puede generar descartes explícitos sin bloquear el panel.
12. Comprueba recuperación ante un error realmente observado. El botón «Reintentar escáner» solicita un reinicio manual y sólo se confirma al recibir un nuevo heartbeat. No fuerces fallos eléctricos ni agotes intencionalmente memoria. La política acota reintentos a tres y mantiene diagnóstico cuando suspende el escaneo; su ejecución sobre hardware permanece pendiente.

## Hoja de resultados para completar

| Equipo autorizado | Wi-Fi recibido | BLE recibido | Classic recibido | Evidencia / canal / MAC observada | Observación |
|---|---|---|---|---|---|
| Android | Pendiente | Pendiente | Pendiente | Pendiente | Anotar si emite y es descubrible |
| Laptop | Pendiente | Pendiente | Pendiente | Pendiente | Anotar banda y modo Bluetooth |
| Router 2.4 GHz | Pendiente | No aplicable salvo que lo soporte | No aplicable salvo que lo soporte | Pendiente | Canal propio del 1 al 11 |
| Equipo Bluetooth | No aplicable salvo que lo soporte | Pendiente | Pendiente | Pendiente | Anotar si BLE o Classic y modo descubrible |

Que un equipo no aparezca no demuestra que el sistema falle: primero verifica si emite en la banda y el protocolo que se está observando. No se debe intentar vincular una MAC privada nueva con una dirección anterior.
