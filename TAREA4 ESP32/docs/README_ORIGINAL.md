# Observatorio ESP32 — versión 2.1.0
**Actualización de identificación:** el panel separa tipo de equipo, marca probable y rol Wi-Fi; amplía CoD/Appearance Bluetooth, interpreta metadatos WPS anunciados y ofrece BLE activo opcional. Los modelos se muestran como anunciados y cada campo tiene su propia confianza. Los detalles y pruebas están en `docs/IDENTIFICACION_2_1.md`. La corrección de país `01` permanece. Actualiza backend y firmware juntos y confirma versión 2.1.0.

Actualización del proyecto existente para ESP32-D0WD-V3, flash de 4 MB y COM6. Se conservan firmware ESP-IDF 5.4.2, backend FastAPI/SQLite y panel HTML. La auditoría, cambios y pruebas están en `docs/AUDITORIA.md`, `docs/MEJORAS.md` y `docs/VALIDACION.md`.

## Inicio por doble clic en Windows 11

1. Extrae el ZIP en una carpeta, por ejemplo `C:\proyectos\esp32-detector`. `INICIAR.bat` debe estar junto a `backend`, `frontend`, `firmware` y `scripts`.
2. Instala **Python 3.12 x64 con el lanzador py**. Si ya tienes Python 3.14, pueden coexistir. Comprueba `py -3.12 --version`.
3. Ejecuta **INSTALAR.bat** una vez. Informa la creación de `.venv` y descarga las dependencias. Requiere Internet sólo durante esta preparación.
4. Ejecuta **INICIAR.bat**. Verifica instalación, rutas y puerto 8000, inicia FastAPI, espera `/api/health` y abre **http://127.0.0.1:8000** en el navegador. Mantén la consola abierta; Ctrl+C detiene el proceso que inició.
5. **No necesitas el ESP32 para abrir el panel.** Verás «ESP32 desconectado — esperando conexión serial». Cuando conectes la placa con firmware v2, el panel separará puerto, firmware y cada escáner.
6. Si algo falla, abre **DIAGNOSTICAR.bat**. Muestra el error, puertos seriales, dependencias, rutas, SQLite y puerto 8000. No cierra otros procesos ni oculta errores. Una instalación antigua que ya ocupe 8000 debe cerrarse antes de usar esta actualización.

La lógica del lanzador se ejecutó y verificó en Linux. Los archivos BAT/PowerShell se revisaron, pero su ejecución nativa en Windows y la carga en tu COM6 siguen **PENDIENTES DE PRUEBA FÍSICA / WINDOWS**. No abras `frontend/index.html` directamente por doble clic.

## Cargar el nuevo firmware sin compilar

Cierra el backend/monitor para liberar COM6. Desde PowerShell, dentro de la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install esptool==4.13.0
.\.venv\Scripts\python.exe -m esptool --chip esp32 --port COM6 --baud 460800 write_flash 0x0 firmware\prebuilt\esp32-detector.bin
```

Esto reemplaza el programa actual del ESP32. Si no conecta, mantén BOOT durante `Connecting...`; si falla la transferencia, utiliza `--baud 115200`. El binario es exclusivo del ESP32 original con al menos 4 MB de flash. Después ejecuta INICIAR.bat. El firmware v1 sigue siendo legible, pero para confirmar escaneo activo y ver telemetría completa necesitas cargar v2.

## Compilar desde el código fuente

En una terminal **ESP-IDF 5.4.2** configurada:

```powershell
cd firmware
idf.py set-target esp32
idf.py build
idf.py -p COM6 flash monitor
```

Cierra el monitor con **Ctrl+]** antes de INICIAR.bat. Para instalar ESP-IDF utiliza la [guía oficial de Espressif](https://docs.espressif.com/projects/esp-idf/en/v5.4.2/esp32/get-started/windows-setup.html). No necesitas instalar ESP-IDF si cargas el binario incluido.

## Usar las mejoras

- En **Estado del sistema**, revisa backend, SQLite, serial, firmware y los tres escáneres. «En vivo» corresponde al enlace web; no prueba por sí solo captura RF. Sólo se declara escaneo activo después de confirmación explícita reciente de la radio.
- Elige **Rápido, Equilibrado o Exhaustivo** y pulsa Aplicar perfil. Se cambian parámetros reales; se aplican al iniciar el siguiente ciclo completo y se espera ACK. No se promete detectar todos los dispositivos.
- En **Calibrar RSSI**, selecciona una dirección propia/autorizada estable, confirma autorización y captura ventanas a **1, 3, 5 y 10 m**. Se requieren cinco lecturas por distancia. Ajusta la duración si hay pocas emisiones. El ajuste calcula RSSI de referencia, n, RMSE y R²; sólo se aplica con parámetros válidos y mediante el botón explícito. La distancia sigue siendo aproximada, con calidad baja y alta incertidumbre.
- Las métricas de tiempos, canales, cola, heap, capturas, descartes y arranques proceden del firmware. «No informado» identifica datos ausentes en versiones antiguas. No se calcula un porcentaje ficticio de equipos detectados.
- La ficha de cada dirección incluye canal, RSSI actual/filtrado, evidencia, privacidad e historial. Los gráficos añaden actividad por canal, observaciones por tecnología y descartes del arranque actual.
- El botón **Reintentar escáner** solicita un reinicio controlado para salir de una suspensión por fallos. Su disponibilidad se confirma sólo al recibir el nuevo heartbeat. No es una garantía de reparar un fallo físico.

Si actualizas una instalación con datos, conserva su carpeta `data` y no sobrescribas `observations.sqlite3` ni `settings.json` con archivos de otra instalación. La migración guarda copia de una base anterior con observaciones (`*.pre-v2.sqlite3`) y conserva filas e IDs. Las copias no se purgan automáticamente. Una base corrupta o de versión futura se conserva y se informa como no disponible. Un JSON de configuración dañado permite abrir el panel con valores predeterminados y queda respaldado cuando guardas su reparación.

## Comandos alternativos y pruebas

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m pytest tests -q
```

Prueba opcional de navegador, que usa solamente datos sintéticos en una base temporal separada:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright==1.51.0
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe tests\ui_check.py
.\.venv\Scripts\python.exe tests\ui_upgrade_check.py
```

Cierra antes el servidor del puerto 8000. La prueba completa de calibración tarda alrededor de medio minuto. Las pruebas PTY se omiten en Windows; la prueba C nativa requiere `cc`. La compilación ESP-IDF verifica ese código para ESP32.

## Captura y límites

| Componente | Información | Límites |
|---|---|---|
| Wi-Fi promiscuo | MAC del transmisor, RSSI, canal, clase de trama y rol AP/estación cuando la cabecera lo permite | Sólo 2.4 GHz, un canal por turno; no todos los equipos transmiten. No guarda contenido de comunicaciones ni SSID; extrae metadatos WPS seleccionados cuando se anuncian. Un AP puede ser hotspot, por eso no se etiqueta automáticamente como router. |
| BLE pasivo | MAC y tipo, RSSI, tipo de anuncio, nombre, UUID, apariencia, Company ID y hasta 32 bytes de datos del fabricante | Modo pasivo predeterminado; opción activa para solicitar respuestas de escaneo. Pueden faltar nombre y otros datos. Sin conexión GATT, sin emparejamiento y sin seguimiento entre direcciones privadas. |
| Classic | Resultados de inquiry, nombre/EIR disponible, clase CoD, RSSI si existe | El inquiry transmite consultas de descubrimiento. Sólo responden equipos descubribles. El sistema no solicita emparejamiento ni conexiones. Puede haber resolución de nombre propia del procedimiento GAP. |
| OUI | Titular oficial del bloque más específico MA-S → MA-M → MA-L | No demuestra el producto final. No se consulta para MAC Wi-Fi locales ni BLE aleatorias/de tipo desconocido. |
| Identificación | Marca probable por titular reconocido o nombre autodeclarado; categoría por CoD, apariencia o términos del nombre | Ni un Company ID ni un fabricante de chip se convierten automáticamente en marca del equipo. Los nombres se pueden modificar. |

Se separan las identidades **tecnología + MAC**. Una MAC Wi-Fi y una Bluetooth no se fusionan, aunque coincidan. No se intenta deduplicar un equipo físico entre tecnologías ni entre rotaciones de MAC. Los conteos son direcciones observadas, no personas ni número garantizado de equipos.

Los cuatro niveles admitidos son Alta, Media, Baja y Desconocida. Se expone además confianza de categoría; un CoD/apariencia declarado aporta evidencia explícita de categoría, sin verificar autenticidad del producto. La implementación conservadora actual produce Media cuando coinciden un titular comercial reconocido y una categoría estructurada, sin contradicción de marca; Baja cuando sólo hay titular o nombre; Desconocida si faltan evidencias. **Alta se reserva para una futura regla respaldada por una identificación explícita verificable.** No hay reglas universales fiables de modelo comercial: se muestra el modelo autodeclarado WPS si existe, identificado como anunciado, o «No identificable». La estructura permite añadir decodificadores documentados; no se inventan modelos para cumplir una lista de marcas.

Las reglas de `data/name_rules.json` cubren las marcas solicitadas y son extensibles; una marca sólo aparece si se observa evidencia coincidente. Algunas categorías no se podrán reconocer y permanecerán desconocidas. Las cadenas de nombre que no sean ASCII se sustituyen por `?` en el firmware para mantener JSON válido; la MAC y el resto de metadatos no cambian.

## RSSI y distancia

El panel muestra la última lectura válida, promedio y mediana de las últimas 15 lecturas aceptadas y filtro exponencial `EMA = alpha * RSSI + (1-alpha) * EMA_anterior`. Se filtra el ruido, sin convertir RSSI en una medición exacta de distancia.

**Por defecto no se muestran metros.** Para habilitarlos, coloca un emisor de referencia a 1 m, registra múltiples lecturas, toma la mediana como `rssi_ref`, ajusta `n` con otras distancias conocidas y marca «Activar estimación con mi calibración». Se aplica:

`d = 10 ** ((rssi_ref - mediana_RSSI) / (10 * n))`

Las categorías son Muy cerca (<1 m), Cerca (1–3 m), Distancia media (3–10 m), Lejos (≥10 m), y Distancia desconocida si no hay calibración o RSSI. No se recorta artificialmente una estimación extrema. El parámetro Tx Power anunciado se registra, pero no se trata como RSSI a 1 m. Las estimaciones son globales y tienen incertidumbre alta; no hay calibración individual por transmisor.

## Panel y datos

- Una página con temas claro/oscuro, métricas de observación y estado del escáner.
- Búsqueda y filtros de marca, categoría, tecnología, RSSI mínimo, fecha de última observación y estado; orden por señal, marca, fechas o conteo.
- Detalle por fila con evidencia, advertencias, lecturas RSSI, metadatos técnicos e historial configurable. Vuelve a abrir el detalle para refrescar su historial.
- Seis gráficos con categorías, marcas, tecnología, intensidad, nuevas direcciones por minuto y observaciones por minuto. Las series temporales cubren los últimos 60 minutos; otros gráficos muestran las direcciones retenidas.
- CSV/JSON exportan **todos** los dispositivos retenidos, independientemente del filtro visible; no exportan el payload de comunicaciones. El CSV neutraliza fórmulas de hoja de cálculo en campos de texto.
- Alertas en pantalla para direcciones nuevas y reapariciones; no envía correos ni notificaciones externas. «Sin señal reciente» indica que venció la ventana de observación, no una salida física confirmada.
- Reiniciar conteo requiere confirmación en pantalla y elimina dispositivos y sus observaciones. El diagnóstico se conserva.
- Retención de 1–365 días, limpieza cada minuto; historial de detalle limitado a 10–5000 lecturas por consulta. El conteo de una dirección retenida es acumulado desde su primera detección, aunque se haya purgado parte de su historial.

Los tiempos del ESP32 son de actividad desde su arranque. Las fechas visibles y los intervalos de presencia se asignan en la computadora al recibir cada evento, se almacenan como UTC y se presentan en la hora local del navegador. No se interpretan como fecha absoluta del reloj del ESP32.

## Planificador, memoria y protocolo

El ciclo predeterminado es Wi-Fi 6 s (canales 1–11, 250 ms/canal), BLE 6 s, Classic 4 unidades × 1.28 s, seguido de una pausa mínima de 100 ms. La resolución de nombre y el controlador pueden extender Classic. Una espera fallida provoca cancelación. Se acotan los reintentos a tres; un fallo persistente deja el escáner suspendido con diagnóstico. Si no se confirma la cancelación, se permite reinicio controlado sólo mientras no se alcance el límite de fallos. El Task Watchdog supervisa las tareas con esperas fragmentadas; la recepción RF y la recuperación física quedan pendientes. La configuración se aplica sólo entre ciclos. La pausa configurable se añade al final de cada ciclo.

Se fija un subconjunto conservador de canales 1–11 para Perú, sin expansión automática por anuncios de otros equipos. El firmware permite ajustar únicamente ese rango. No implementa cambios a otros países. La cola de captura tiene 32 registros fijos; una cola llena descarta observaciones y aumenta `queue_dropped`. La caché de deduplicación tiene 128 entradas, por lo que en ambientes muy densos puede expulsar direcciones antes del intervalo; el backend aplica además su propio control. Serial usa 115200 baudios y JSON Lines. No hay garantía de captura completa en ambientes saturados ni mientras se observan otras tecnologías.

El callback Wi-Fi sólo copia la cabecera relevante a una cola. La serialización JSON, almacenamiento, identificación y cálculos se realizan fuera de ese callback y, salvo extracción básica de anuncios, en la computadora. Partición de aplicación: 3 MiB dentro de flash de 4 MB, sin OTA. El resto no se usa para guardar capturas. El firmware no se conecta a redes Wi-Fi, no inyecta tramas, no desautentica y no ejecuta servidores en el ESP32.

Consulta `docs/PROTOCOLO.md` para los campos de eventos y endpoints.

## Pruebas

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

O:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas utilizan bases temporales y datos sintéticos aislados. No insertan registros de prueba en producción. La integración PTY sólo se ejecuta en POSIX y se omite en Windows; la prueba del parser C nativo requiere un compilador `cc` y se omite si no existe. La compilación ESP-IDF sí verifica el parser C para el ESP32.

Para repetir las pruebas visuales automatizadas, instala opcionalmente Playwright y Chromium y ejecuta `tests/ui_check.py`; usa una base temporal y un puerto virtual, sin hardware real. El detalle de las verificaciones efectuadas está en `docs/VALIDACION.md`.

## Solución de problemas

| Síntoma | Acción |
|---|---|
| COM6 ocupado / acceso denegado | Cierra `idf.py monitor`, Arduino Serial Monitor y otras instancias del backend. |
| Puerto inexistente | Verifica el puerto real y usa un cable USB de datos; cambia el puerto en Configuración. |
| Puerto abierto, firmware sin señal | Comprueba 115200 baudios, firmware ESP32 original y alimentación. Revisa `monitor` con el backend detenido. |
| No aparecen celulares | Espera varios ciclos; verifica 2.4 GHz, emisiones Wi-Fi y anuncios BLE. Un celular no necesariamente es descubrible en Classic. |
| MAC privada o marca desconocida | Es una limitación esperable; el sistema no busca desanonimizar ni inventar la marca. |
| Metros no disponibles | Activa la calibración sólo después de medir un emisor a distancias conocidas. |
| Cambios pendientes | Espera al siguiente ciclo. Con valores máximos el ciclo puede tardar varios minutos. Mira fase, heartbeat y diagnóstico. |
| Interfaz sin actualizar | Comprueba que la URL sea `http://127.0.0.1:8000` y que la terminal siga ejecutando uvicorn. |
| Caída de memoria o reinicios | Revisa `free_heap` y `queue_dropped` en Diagnóstico. Valida con tu unidad real antes de uso sostenido. |

## Estructura

`firmware/`: proyecto completo ESP-IDF y binario compilado. `backend/`: API, serial, identificación, SQLite. `frontend/`: panel sin CDN (incluye la fuente Roboto Slab en `frontend/fonts/`). `data/`: registros oficiales y reglas. `scripts/`: instalación, ejecución, carga y actualización. `tests/`: validación de parser, identificación, almacenamiento, API y serial. `docs/`: protocolo, evidencia de compilación y pruebas pendientes.
