# Validación de la actualización 2.0 — 8 de noviembre de 2026

## Resultado comprobado

| Verificación | Resultado |
|---|---|
| Proyecto de partida | ZIP suministrado de 49 archivos, idéntico en SHA-256 a la entrega previa; se conserva arquitectura y funcionalidad |
| Auditoría previa | Inicio correcto sin COM6; fallo reproducido con settings.json truncado. El fallo concreto de la PC del usuario no se pudo diagnosticar sin sus logs |
| Firmware | Compilación y enlace correctos con ESP-IDF 5.4.2, target esp32, commit f5c3654a1c2d2a01f7f67def7a0dc48e691f63c0 |
| Flash | Aplicación de **1,217,504 bytes** (`0x1293e0`), partición 3 MiB, **61 % libre**; cabe en flash de 4 MB |
| IRAM | **105 598 bytes**, 80.56 % utilizada; 25 474 bytes de margen estático |
| DRAM estática | **63 012 bytes**; no representa el heap que quedará durante ejecución |
| Impresión JSON | Buffer reutilizable de 4096 bytes; cola 32 registros; caché de deduplicación 128 |
| Backend | **46 pruebas aprobadas**, incluidas las 25 originales, CPython 3.12.14/Linux |
| Panel sin placa | `/`, `/api/health` y `/api/state` disponibles; COM6 ausente sin bloqueo |
| Configuración dañada | Se conserva el archivo, se usan valores predeterminados y el guardado reparado hace copia del original |
| SQLite no disponible | Panel y diagnóstico accesibles; la base corrupta no se reemplaza; exportación responde 503 |
| Migración | Conserva ID 42, conteo y fechas del fixture antiguo, crea copia previa, añade columnas/índices y no degrada un esquema futuro |
| Identificación | OUI más específico, prefijos ambiguos, MAC local/privada, chip frente a marca, CoD/apariencia y evidencia |
| Protocolo | v1/v2, alias type/technology/timestamp, incompatibilidades y contradicciones rechazadas; heartbeat extendido validado |
| Serial | Pyserial real con PTY: fragmentos, longitud excesiva, ACK, desconexión/reconexión; sólo simula el extremo del dispositivo |
| Recuperación | Política de límite de tres fallos ejecutada en C nativo; integración de TWDT y RTC noinit compilada; recuperación física no ejecutada |
| Perfiles | Prueba que rápido/equilibrado/exhaustivo modifican valores de configuración y el comando real enviado a serial |
| Lanzador | Se ejecutó `scripts/launcher.py start --smoke-test --no-browser`: inició uvicorn, esperó salud y validó HTML sin COM6, y terminó su propio proceso |
| Conflicto de puerto | Pruebas de rechazo de servicio ajeno y reutilización del servidor reconocido, sin matar procesos |
| Navegador base | Playwright/Chromium: filtros, detalle, calibración manual, configuración, exportación CSV, diagnóstico, temas, móvil y reinicio |
| Navegador ampliado | Perfiles, asistente con cuatro ventanas de 5 s y lecturas sintéticas en tiempo real, ajuste aplicado, diagnóstico, móvil y backend detenido reflejado |
| Offline | Panel arrancado y probado con solicitudes externas bloqueadas; no se intentó ninguna solicitud externa |
| Base oficial | Se conserva IEEE MA-L/MA-M/MA-S: 54 399 filas fuente, 54 396 prefijos únicos; 4 065 Company Identifiers SIG |
| Datos de producción | Sin observaciones ni ajustes de prueba precargados; fixtures temporales aislados |

Las evidencias de ejecución se incluyen en `build_evidence.txt`, `pytest_evidence.txt`, `ui_evidence.txt`, `ui_upgrade_evidence.txt` y `launcher_evidence.txt`. La advertencia de deprecación de AnyIO/Starlette en el cliente de pruebas no produjo fallos. Los hashes de binarios y fuentes están en firmware/prebuilt. La tabla de particiones conserva offsets 0x1000/0x8000/0x10000; el combinado se carga desde 0x0.

La compilación en este entorno usó `IDF_COMPONENT_MANAGER=0` porque el gestor de componentes consulta procesos no visibles dentro del contenedor. Sólo se utilizan componentes incluidos en ESP-IDF; no se cambió ninguna biblioteca de radio. Herramientas: CMake 3.30.9 y Ninja 1.11.1.3. En la terminal Windows ESP-IDF se utiliza `idf.py build` normalmente.

## PENDIENTE DE PRUEBA FÍSICA / WINDOWS

No se ha conectado ni cargado el ESP32 del usuario, abierto su COM6 ni ejecutado un BAT o PowerShell nativo en Windows 11. Se ha probado la lógica Python de lanzamiento en Linux, con apertura de navegador desactivada durante la prueba automática. La apertura del navegador predeterminado en Windows queda pendiente.

Captura real de Wi-Fi/BLE/Classic, alternancia RF, inicialización sobre silicio, heap libre/mínimo, estabilidad prolongada, recuperación frente a fallos reales y precisión de distancia quedan pendientes. Compilar no demuestra esas propiedades. La guía `PRUEBAS_FISICAS.md` permite registrar Android, laptop, router y dispositivo Bluetooth propios/autorizados.

Ninguna métrica de radio se inventa para rellenar el panel. V1 muestra «No informado» donde no existen métricas. El firmware cuenta eventos y tiempos de escucha confirmados por APIs/callbacks; no conoce el número de equipos físicos presentes. No se vinculan direcciones privadas, tecnologías ni rotaciones. Sin información verificable, un modelo comercial continúa «No identificable».
