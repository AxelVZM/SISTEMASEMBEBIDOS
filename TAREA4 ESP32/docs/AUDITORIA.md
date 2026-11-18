# Auditoría previa — 8 de noviembre de 2026

Se inspeccionaron los 49 archivos de la versión suministrada `esp32-detector(1).zip`. Su SHA-256 coincide con la entrega original; no se encontraron cambios externos en el archivo. Se conservan firmware ESP-IDF, FastAPI, SQLite, frontend sin CDN y las API existentes. La base incluye MA-L/MA-M/MA-S y Bluetooth SIG; no es necesario reconstruirla.

| Componente | Hallazgo | Evidencia / causa | Solución | Prioridad | Archivo |
|---|---|---|---|---|---|
| Inicio | Configuración inválida aborta el servidor | Reproducido con `settings.json` truncado: Pydantic ValidationError durante lifespan | Cargar valores predeterminados, conservar el archivo inválido y explicar el error | Crítica | backend/main.py |
| Inicio Windows | No abre automáticamente el navegador ni verifica puerto, instalación o rutas | Inspección del script run.ps1 | INICIAR.bat + lanzador con comprobaciones, espera de salud y consola visible | Crítica | scripts/run.ps1, scripts/launcher.py |
| Panel sin ESP32 | La versión original sí responde 200 en `/` y `/api/state` sin COM6 | Prueba de inicio en directorio temporal | Conservar este comportamiento y probarlo nuevamente | Alta | backend/main.py |
| Causa del fallo del usuario | No se proporcionaron logs de Windows | No puede atribuirse el fallo concreto a Python, puerto o configuración sin diagnóstico | DIAGNOSTICAR.bat, salud y diagnóstico visibles | Alta | scripts/launcher.py |
| SQLite | Error al abrir base puede abortar inicio; no se informa estado separado | Conexión directa sin contención del error en Runtime | Modo degradado explícito y reintento sin sustituir ni borrar datos | Alta | backend/main.py, backend/store.py |
| Presencia | Cualquier evento válido renueva firmware_online; no demuestra escaneo activo | Inspección serial_loop y render | Diferenciar serial, firmware, escáner y heartbeat reciente | Alta | backend/main.py, frontend/app.js |
| Firmware | API críticas usan ESP_ERROR_CHECK y reinicios sin límite | Inspección de inicialización y planificador | Máquina de estados, reintentos acotados, modo de recuperación estable y TWDT | Alta | firmware/main/main.c |
| Memoria | Cola limitada ya existe; serialización aún asigna buffer de impresión por evento | Inspección de emit y writer | Impresión preasignada, colas fijas y contadores de pérdidas medibles | Media | firmware/main/main.c |
| Telemetría | Sólo heap libre, uptime, fase y descartes | Esquema Status 1.0 | Protocolo 2 compatible con v1, heap mínimo, tiempos, canales, reinicios y saturación | Alta | firmware/main/main.c, backend/models.py |
| Historial | Metadatos almacenados, identificación recalculada, sin snapshot de evidencia/canal indexado | Esquema devices/observations | Migración aditiva con snapshots de identificación y canal, sin pérdida de filas | Media | backend/store.py |
| Calibración | Ajuste manual; no captura mediciones a distancias conocidas | Inspección de configuración | Sesiones de calibración con 1/3/5/10 m, ajuste y validación de parámetros | Media | backend/calibration.py, frontend/app.js |
| Perfiles | No existen perfiles rápidos/equilibrados/exhaustivos | Esquema Settings | Perfiles que cambian parámetros enviados al firmware y requieren ACK | Media | backend/models.py, backend/main.py |
| Identificación | No distingue explícitamente proveedor de radio/marca y no publica identification_evidence | Inspección del motor | Campos separados, evidencia compatible y tratamiento de conflictos | Media | backend/identify.py |

Prueba base: 25 tests aprobados antes de editar. El fallo de configuración truncada sí se reprodujo; el fallo específico de la PC del usuario sigue sin diagnóstico directo. No se ha abierto COM6 físico ni probado recepción RF en este entorno.
