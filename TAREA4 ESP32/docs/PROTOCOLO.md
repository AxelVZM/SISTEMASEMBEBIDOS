# Protocolo y API — versión 2

## Compatibilidad serial

Se mantiene USB/UART 115200 8N1, JSON Lines, el evento `observation` y todas las rutas originales. El receptor admite firmware v1 y v2. El protocolo v2 añade un campo `type`, sin romper el nombre histórico `event`. No acepta versiones futuras silenciosamente.

| Mensaje | Campos de versión 2 | Compatibilidad |
|---|---|---|
| Detección | `event:observation`, `type:detection`, `v:2`, `tech`, `mac`, `uptime_ms`, RSSI y metadatos disponibles | Admite el formato v1 original. También normaliza `technology` a `tech`, `timestamp_ms` a `uptime_ms` y `protocol_version` a `v`; contradicciones se rechazan |
| Estado | `event:status`, `type:status`, `v:2` y telemetría | Se envía en cambios de fase importantes |
| Heartbeat | `event:heartbeat`, `type:heartbeat`, `v:2` y telemetría | Cada 3 segundos; el formato antiguo `status` también renueva presencia |
| Error | `event:error`, `type:error`, `v:2`, `message` | No se usa como prueba de escaneo activo |
| Configuración aplicada | `event:ack`, `v:2`, `id`, `state:applied` | Se conserva ACK v1; sólo confirma el ID pendiente correspondiente |

Una línea de más de 4096 bytes se descarta hasta el salto de línea siguiente. Se reconstruyen lecturas fragmentadas y se rechazan JSON/UTF-8 inválidos. Los logs de ROM no se tratan como observaciones ni se guardan como contenido arbitrario. Las líneas corruptas y excesivas incrementan diagnósticos.

El firmware acepta comandos de hasta 1023 bytes. `command:configure` lleva `id`, `channels`, `wifi_ms`, `dwell_ms`, `ble_seconds`, `classic_units`, `bt_interval_seconds`, `dedup_ms`, `min_rssi`. La configuración se aplica entre ciclos. `command:recover` solicita reinicio manual, borra la racha de recuperación y exige un nuevo heartbeat para confirmar disponibilidad. No agrega conexiones Wi-Fi, emparejamiento ni comandos de ataque.

### Telemetría

`firmware`, `boot_id`, `phase`, `uptime_ms`, `free_heap`, `minimum_free_heap`, `queue_dropped`, `current_channel` cuando se conoce, `events_captured`, `events_sent`, `queue_depth`, `queue_capacity`, `queue_high_water`, `dedup_suppressed`, `rssi_filtered`, `json_failures`, `serial_failures`, `wifi_listen_ms`, `ble_scan_ms`, `classic_scan_ms`, `channel_events[11]`, `channels_visited`, `boot_count` si NVS está disponible, `reset_reason`, `scanner_recoveries`, `consecutive_failures`, `wifi_initialized`, `bluetooth_initialized`, `wifi_scanning`, `ble_scanning`, `classic_scanning` y `last_capture_ms` cuando hubo capturas.

Los tiempos se acumulan durante ventanas que el controlador confirmó activas; Wi-Fi desde activar promiscuo hasta detenerlo, BLE/Classic desde callbacks de inicio hasta fin/cancelación. Son cobertura temporal del escáner, no medición de todo el tiempo físico de antena ni porcentaje de equipos detectados. `queue_high_water` es el máximo de profundidad observado al encolar. Los contadores se reinician con el arranque; `boot_count` se guarda una vez por arranque en NVS. La racha de fallos utiliza RTC no inicializada y se borra al encendido en frío o tras una etapa estable; no es un conteo vitalicio de fallos.

`events_captured` cuenta eventos compatibles antes de deduplicación y umbral; `events_sent` cuenta detecciones serializadas, no confirma que el PC las haya almacenado. Descartes de cola, duplicados suprimidos, filtro RSSI, fallos JSON y UART se muestran separados. El ESP32 no puede determinar si la computadora sigue conectada al extremo USB del convertidor UART: `serial_host_detection:not_supported`. El backend sí comprueba su puerto real. Los campos ausentes de v1 aparecen como «No informado», no como métricas inventadas.

## Salud y diagnóstico

`GET /api/health` responde incluso con COM6 ausente, configuración ilegible o SQLite no disponible. `status:degraded` indica un problema local; no se oculta con una base ficticia. El panel sigue sirviéndose. Se separan backend, SQLite, puerto, firmware y cada escáner. Sólo se declara escáner activo cuando hay estado reciente (12 s), bandera de actividad afirmativa y fase compatible; v1 no confirma las nuevas banderas.

`GET /api/diagnostics` incluye salud, última telemetría, errores recientes, inválidos, reconexiones, cambios de arranque observados, clientes/errores WebSocket, configuración pendiente y observaciones no almacenadas por fallo de base. No contiene credenciales ni payloads de comunicaciones.

## Endpoints

Se conservan `/`, `/assets`, `/api/state`, `/api/settings` (GET/PUT), `/api/devices/{key}/history`, `/api/export/csv`, `/api/export/json`, `/api/errors`, `/api/reset` y `/ws`.

| Ruta nueva | Uso |
|---|---|
| `GET /api/health` | Salud real por componente |
| `GET /api/diagnostics` | Diagnóstico sin secretos |
| `GET /api/ports` | Puertos seriales enumerados por pyserial |
| `GET /api/profiles` | Parámetros de los tres perfiles |
| `POST /api/profiles/{rapid,balanced,exhaustive}` | Guarda tiempos y envía configuración al firmware conectado |
| `POST /api/scanner/recover` | Solicita recuperación; 409 sin puerto abierto |
| `POST /api/calibration/start` | `{device_id, authorized:true}`; dirección ya observada |
| `GET /api/calibration/{id}` | Estado, lecturas y ajuste calculado |
| `POST /api/calibration/{id}/capture` | `{distance:1/3/5/10, seconds:5..120}`; una ventana a la vez |
| `POST /api/calibration/{id}/apply` | Aplica sólo un ajuste válido y completo |

Calibración usa lecturas aceptadas dentro de la ventana para una sola tecnología+MAC, sin enlazar rotaciones. Requiere cinco lecturas por distancia, ajusta RSSI contra `log10(d)` por mínimos cuadrados, usa medianas, calcula RMSE y R² y rechaza parámetros fuera de `n=1..6`, RSSI a 1 m entre -100 y -20, o R² menor que 0.5. La distancia sigue teniendo calidad baja/incertidumbre alta y el ajuste se aplica globalmente por decisión explícita.

SQLite se migra aditivamente a esquema 2, preserva claves/filas y crea una copia `*.pre-v2.sqlite3` antes de migrar bases antiguas con observaciones. Añade canal indexado y snapshot de identificación/evidencia por observación. No inventa identificación histórica ausente. Un esquema futuro no se degrada ni se sobrescribe. Una base corrupta se conserva; se informa el error y se reintenta abrir cada 15 s. Las sesiones de calibración comparten la retención configurada. Las copias previas a la migración quedan bajo control del usuario y no se purgan automáticamente.

La aplicación permanece local en `127.0.0.1:8000`; orígenes WebSocket/HTTP distintos del servidor local se rechazan. No se añade autenticación ni publicación remota. El frontend sigue sin CDN y con funcionamiento offline después de instalar dependencias.

## Extensión de identificación 2.1.0

Se conserva v=2 y se admiten mensajes anteriores. Las observaciones añaden opcionalmente name_source, name_complete, wps_manufacturer (64), wps_model_name (32), wps_model_number (32) y wps_primary_device_type (16 dígitos hex). La configuración añade ble_active (predeterminado false), opcional también en firmware al recibir comandos antiguos. El heartbeat informa ble_scan_mode cuando Bluetooth está configurado. Actualiza backend y firmware juntos. El esquema SQLite se conserva en 2; los metadatos y evidencias se guardan en JSON existente. Ver IDENTIFICACION_2_1.md.
