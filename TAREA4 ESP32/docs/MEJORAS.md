# Cambios implementados sobre el proyecto existente

Se conserva la arquitectura, nombres de endpoints originales, datos previos, base oficial y diseño del panel. No se añadieron dependencias Python externas: se usaron las ya existentes y la biblioteca estándar. Se eliminó una línea duplicada de `typing_extensions` del archivo de versiones fijadas.

| Mejora | Implementación | Verificación y límite |
|---|---|---|
| 1 | FSM WIFI_SCAN → BLE_SCAN → BT_CLASSIC_SCAN → PROCESS_EVENTS → IDLE, con ERROR_RECOVERY | Compilación ESP32; alternancia RF pendiente |
| 2 | Conserva captura y rotación 1–11, añade eventos por canal y canales recorridos | Parser C y compilación; recepción real pendiente |
| 3 | Conserva captura independiente de Internet y de la red del PC | Sin dependencias de red en inicio; emisiones reales pendientes |
| 4 | Cola fija de 32, caché 128, impresión JSON preasignada de 4096 bytes, contadores de fallos | Memoria estática medida en compilación; heap en ejecución pendiente |
| 5 | TWDT por tareas, espera fragmentada con alimentación del watchdog, tres reintentos como máximo, suspensión diagnosticable y recuperación manual | Política de límites ejecutada en C nativo; fallos físicos pendientes |
| 7 | Heartbeat 3 s, heap/mínimo, fases, canal, contadores, colas, tiempos y reinicios | Esquema probado; datos de hardware no inventados |
| 11 | Conserva 54 396 prefijos oficiales, consulta cacheada acotada, proveedor de radio separado de marca | Pruebas OUI y ambigüedad de prefijos |
| 12 | Conserva BLE/EIR, Company ID, nombres y UUID; expone titular SIG por separado | Parser/modelos y reglas probados; descubrimiento real pendiente |
| 13 | Clasificación por evidencia, añade Altavoz desde CoD; no infiere celular por OUI | Pruebas de CoD/apariencia y nombres |
| 15 | Advertencia explícita de MAC posiblemente aleatoria/local; sin enlace entre rotaciones | Pruebas Wi-Fi local y BLE privado |
| 16 | identification_evidence y confianza; separa categoría explícita de marca probable y contempla contradicciones | Pruebas de evidencia y fuente comercial |
| 19 | Mantiene WS, añade salud/diagnóstico al estado, reconexión y comprobación HTTP de respaldo | Navegador: pérdida real del proceso backend reflejada |
| 21 | RSSI actual/EMA, intensidad, estimación calibrada y calidad baja explícita | Estadística y navegador probados |
| 24 | Ficha amplía canal, conteo, proveedor, titular SIG, evidencia, privacidad e historial; refresca mientras está abierta | Navegador y API |
| 25 | Nueve gráficos, incluidos observaciones por tecnología, canales y descartes reales | Sin fixtures en producción; navegador probado |
| 29 | Siete estados separados y métricas reales; legado muestra no informado | Salud exige bandera positiva, fase compatible y estado reciente |
| 30 | INICIAR.bat, INSTALAR.bat, DIAGNOSTICAR.bat y lanzador estándar con espera, puerto, dependencias y navegador | Lógica/lanzador real probado en Linux; BAT y apertura nativa de navegador pendientes en Windows |
| 31 | Migración aditiva, copia previa de bases antiguas con datos, índices de canal y snapshots de evidencia | Conserva IDs, fechas y conteos; pruebas de migración y esquema futuro |
| 33 | JSON Lines v1/v2, límites, fragmentos, normalización, rechazo de contradicciones, recuperación serial | Pyserial real con PTY; COM6 físico pendiente |
| 35 | Panel sin CDN, base local y arranque sin solicitudes externas | Prueba de navegador restringida a localhost; instalación/actualización opcional requiere Internet |
| 36 | Diagnóstico serial, SQLite, configuración, protocolo, WS, firmware y reinicios | Casos corruptos, puerto inexistente y API probados |
| 41 | Asistente 1/3/5/10 m, ventanas reales, medianas, ajuste, RMSE/R², aplicación explícita | Flujo completo en navegador con lecturas sintéticas temporales; precisión física pendiente |
| 44 | Rápido (2.2 s Wi-Fi/2 s BLE/2 unidades Classic), Equilibrado (6/6/4), Exhaustivo (16.5/15/8) | API prueba parámetros enviados y espera ACK; duración RF física pendiente |
| 45 | Calidad por tiempos, canales, capturas, colas, descartes, último evento y arranques | No calcula porcentaje de dispositivos detectados ni total físico |

## Archivos nuevos

`INICIAR.bat`, `INSTALAR.bat`, `DIAGNOSTICAR.bat`, `scripts/launcher.py`, `backend/runtime.py`, `backend/calibration.py`, `firmware/main/recovery_policy.h`, `tests/test_upgrade.py`, `tests/ui_upgrade_check.py`, `docs/AUDITORIA.md`, `docs/MEJORAS.md`, `docs/PRUEBAS_FISICAS.md` y evidencias nuevas de pruebas.

## Archivos modificados

`backend/main.py`, `models.py`, `parser.py`, `store.py`, `identify.py`, `requirements-lock.txt`; `firmware/main/main.c` y binarios/checksums; `frontend/index.html`, `app.js`, `style.css`; `scripts/install.ps1`; prueba C existente; README, protocolo y validación. El proyecto y la tabla de particiones ESP-IDF se conservan. `requirements.txt` no requiere paquetes adicionales.

## Cambios de comportamiento

- Un archivo de configuración inválido ya no aborta FastAPI: se usan valores predeterminados y se advierte. Al guardar una configuración reparada se conserva copia del archivo inválido.
- SQLite no disponible deja el panel en modo degradado; no se sustituye por datos ficticios ni se elimina la base dañada. Las exportaciones que requieren DB responden 503.
- «Escáner activo» requiere heartbeat reciente con bandera y fase compatibles. El firmware v1 sigue produciendo observaciones, pero no puede confirmar las nuevas métricas.
- Las métricas de captura son por arranque y reflejan ventanas/cargas observadas, no garantía de cobertura de todos los equipos.
- La migración guarda snapshots sólo para observaciones nuevas. Los registros antiguos mantienen metadatos e IDs; no se inventa evidencia histórica.
- El lanzador reutiliza sólo un servidor reconocido de versión 2; ante otro servicio en 8000 explica el conflicto y no cierra procesos ajenos.
- La prueba de calibración requiere cinco observaciones aceptadas por distancia. Un equipo que no anuncia suficientemente debe producir «lecturas insuficientes».

## Pendiente

Pruebas físicas de captura, alternancia, estabilidad/heap, recuperación y precisión RSSI con el ESP32 del usuario. Ejecución de BAT/PowerShell y apertura del navegador predeterminado en Windows 11. No se ha identificado la causa exacta del fallo original de la PC por ausencia de sus logs; sí se corrigió el fallo de inicio reproducido y se agregaron herramientas para diagnosticar los demás casos.
