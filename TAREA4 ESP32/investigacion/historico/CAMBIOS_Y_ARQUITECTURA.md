# V7.2: clasificación embebida por evidencia

`device_classifier.h` calcula el tipo en la placa. `announcements.h` extrae Primary Device Type WPS (0x1054); `count_core.h` conserva ese tipo y el de P2P entre recepciones. BLE conserva Appearance y marca cambios contradictorios. Las decisiones distinguen tipo anunciado, palabra sugestiva, rol AP, conflicto y ausencia de evidencia.

No se clasifican equipos usando el bit U/L, el fabricante del módulo ni el SSID. El rol AP es una función de red; no demuestra que el equipo sea un router físico. No se hacen conexiones activas a los equipos observados ni se introducen identidades manuales.

La telemetría, el filtro de tipo, Detalles, CSV y el complemento AWS reciben el resultado con su fuente. El formato CSV sigue siendo de 16 columnas: la clasificación se añade a `fuente` y participa en el hash de cambios. Los registros históricos siguen siendo legibles.

## Base heredada

# Extensión V7.1: red y nube opcionales

Se conserva V7 como base. `network_config.h` valida ajustes; `network_runtime.h` guarda en NVS y coordina conexión, hora y subida; `ap_capabilities.h` extrae capacidades anunciadas. Los callbacks de captura y el conteo conservan su arquitectura, con campos nuevos de AP.

El bucle sigue procesando USB, registro, periféricos y watchdog durante una operación de red. La asociación y espera de reloj se gestionan por estados; HTTPS se ejecuta en una tarea aparte. Se detienen la recepción y el salto de canales durante la operación, y no se inicia una ventana BLE hasta reanudar la captura. No es recepción de radio ininterrumpida ni un sistema con plazos de tiempo real demostrados.

La tarea HTTPS usa una instantánea y no accede a las tablas de captura. La instantánea no se libera hasta que termina la tarea. Configurar u olvidar una red durante un envío programa su cancelación sin liberar buffers que todavía estén en uso. El resultado y los límites se documentan en `EMPEZAR_AQUI.md`.

El registro mantiene rutas y esquema V7; la configuración de red usa el espacio NVS independiente `orbita_net71`. No se incorporan inventarios manuales, agrupación de MAC como identidades, ni atribuciones de modelo sin evidencia.

## Arquitectura heredada de V7 (modo sin nube)

# V7.0: sistema embebido dedicado al conteo

Nombre propuesto: **Sistema embebido autónomo basado en ESP32 para detección y evaluación del conteo de dispositivos emisores Wi-Fi y Bluetooth LE**. La salida validable inicial es un conteo de direcciones; la equivalencia con equipos físicos se evalúa mediante ensayos.

| Bloque | Implementación |
|---|---|
| Entrada Wi-Fi | Radio promiscuo: gestión/datos, dirección transmisora, canales 1–11, 2,4 GHz |
| Entrada BLE | Anuncios pasivos; dirección + tipo BLE como clave |
| Planificación de radio | Ventanas automáticas 10 s Wi-Fi / 2 s BLE; no recepción simultánea |
| Captura | Callbacks breves a colas FreeRTOS: 64 eventos Wi-Fi, 16 BLE |
| Estado | 96 filas Wi-Fi, 32 BLE; actualiza RSSI EMA y última recepción |
| Conteos | Calculados en el ESP32 con edad <60 s; por protocolo, sin sumarlos |
| Memoria llena | Conserva filas recientes, reemplaza antiguas y reporta nuevas observaciones omitidas |
| Evidencia complementaria | IEEE completo, Company ID/SIG y nombres/campos WPS/P2P si se anuncian |
| Salidas locales | OLED SSD1306, LED externo y reloj DS3231 opcionales |
| Registro | CSV LittleFS: dos segmentos de 128 KiB, búfer 4 KiB, vaciado cada 10 s, resúmenes cada 30 s |
| Pantalla externa | HTML offline + Web Serial; no ejecuta la captura ni la decisión del conteo |
| Supervisión | Reintento Wi-Fi cada 5 s, salida de ventana BLE atascada, reintento de inicialización BLE cada 60 s, reprobe de accesorios/flash cada 30 s, watchdog de tarea 15 s |
| Evaluación | Asistente del navegador para comparación de conteos, sin etiquetas para el clasificador |

## Funciones retiradas de la entrega

Inventario manual y sus comandos/formularios, distancia por RSSI, clasificación de locales, tablas de entornos y relaciones, agrupación de supuestas identidades, huellas y clasificador experimental, cliente GATT, mDNS y SSDP/UPnP. No se conectan redes, no se abren servicios HTTP/SoftAP ni se solicitan conexiones BLE. Se mantiene el rechazo de peticiones de seguridad BLE y el nombre anunciado como dato sin autenticar.

El uso de Preferences queda limitado a un indicador de inicialización del almacenamiento. Los registros de inventario antiguos que pudieran quedar en NVS de una placa no se leen, utilizan ni borran automáticamente.

## Memoria y registro

IEEE conserva 54.220 asignaciones MA-L/MA-M/MA-S y consulta de prefijo más largo, con nombres comprimidos sin pérdida y entradas compactas. La decodificación usa un pequeño búfer estático en el hilo principal; no se llama desde callbacks ni en tareas concurrentes. Los resultados se copian a String antes de otra consulta. No se cambian nombres ni se elimina parte de la base para ahorrar espacio.

Los registros de estado/identificación recorren cuatro ranuras cada 500 ms: nominalmente hasta 16 s para volver a una ranura, más vaciado a flash; no son una cronología por trama. Resúmenes del conteo cada 30 s. Retención depende de cambios/actividad; no se promete una duración fija. La exportación usa una instantánea de tamaños y bloques base64 de 288 bytes, para preservar UTF-8 y no parar la captura. Puede extender temporalmente un segmento durante descarga con límite adicional de 64 KiB. Se cancela por falta de progreso USB.

Archivos flash V7: `/registro_v7_actual.csv` y `/registro_v7_anterior.csv`. No se borran archivos anteriores V6. Un montaje fallido después del primer uso no provoca formato automático; se informa error y se reintenta montar. Si persiste, respalda lo recuperable y diagnostica la partición con la placa; no habilites borrado total para ocultar el fallo.

## Condición de sistema embebido

El ESP32 ejecuta firmware dedicado al encender, captura/procesa/almacena dentro de recursos acotados y puede funcionar con alimentación USB independiente. El navegador solo presenta y evalúa datos; los accesorios locales mejoran la demostración pero no son obligatorios para ser embebido. El watchdog es supervisión ante bloqueos, no una prueba de tiempo real duro. OLED, flash y radio tienen tiempos que deben medirse en hardware antes de garantizar plazos.

La carcasa, montaje final y prueba de autonomía se documentan, no se consideran físicamente realizados. La campaña de latencia/cola/pérdidas sigue pospuesta.

Un corte abrupto puede perder el búfer aún sin vaciar y observaciones todavía pendientes de recorrer; no se promete persistencia de cada evento inmediatamente. Guarda una copia antes de cambios de firmware importantes. Los roles AP/cliente pueden solaparse en una dirección, por lo que tampoco deben sumarse como equipos diferentes.
