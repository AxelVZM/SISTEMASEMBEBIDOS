# Verificación V7.2: clasificación de tipo

Compilación real para ESP32 clásico, Arduino-ESP32 3.3.2 y Huge APP: **2 951 799 / 3 145 728 bytes (93 %)**. Globales: **103 876 / 327 680 bytes (31 %)**. No se ha probado en la placa física ni contra un servidor real.

Se ejecutaron pruebas nuevas de categorías WPS/P2P y Appearance BLE; celular/teléfono, laptop, router, proyector y otras categorías; palabras sugestivas, ausencia de evidencia, conflictos, persistencia de tipo P2P, tamaño/duplicación del atributo 0x1054 y descarte de inferencias basadas solo en SSID/fabricante. También se verificó que Canon no se convierta en proyector por una confusión de nombre.

Se repitieron núcleo Wi-Fi/BLE con 50 000 entradas malformadas, registro CSV/exportación, operación de red y los 11 tests del backend. El panel se probó en DOM simulado para columna de tipo, filtro, fuente en Detalles, compatibilidad anterior, rechazo de categorías inválidas y las funciones existentes. Estas pruebas verifican las reglas y la integración, **no estiman la precisión de clasificación de aparatos reales**.

No se ha entrenado un modelo de aprendizaje automático ni se declara una precisión empírica. Las coincidencias por nombre son heurísticas visibles como Posible. La campaña de latencia/colas/pérdidas permanece pendiente.

## Historial de verificación de la base V7.1

# Verificación V7.1 — 20 de octubre de 2026

## Compilación real para ESP32

Se compiló el firmware final con Arduino CLI 1.3.1, Arduino-ESP32 3.3.2 y GCC Xtensa 14.2.0 para ESP32 clásico, 4 MB y partición **Huge APP**:

- Programa: **2 945 171 / 3 145 728 bytes (93 %)**.
- Variables globales: **102 724 / 327 680 bytes (31 %)**.
- Espacio restante tras globales: **224 956 bytes**; no equivale al heap libre durante BLE/TLS.

Se comprobó que los headers finales del ZIP coinciden con los usados por esa compilación, excluyendo las directivas `#line` que agrega Arduino. La compilación no sustituye una carga ni una prueba física.

## Pruebas ejecutadas

- Núcleo Wi-Fi/BLE: tramas, roles, SSID, EMA, TTL y overflow de reloj; capacidad 96/32, reemplazo de filas antiguas, nombres y conflictos BLE; 50 000 entradas malformadas/aleatorias.
- IEEE: 54 220 prefijos, 108 399 consultas de límites, rechazo por tipo de dirección, 10 000 MAC aleatorias y conservación de registrantes múltiples. Se conservan idénticos los datos IEEE de V7.
- SIG: las 4 049 denominaciones coinciden con sus vectores; datos y núcleo BLE idénticos al V7 adjunto.
- Periféricos y journal: detección opcional, RTC/UTC, OLED, conservación del montaje, esquema CSV de 16 columnas, rotación, exportación UTF-8/secuenciada y comandos USB acotados. El límite de comando pasa a 1 536 bytes para configuración de red.
- Configuración de red: SSID/clave/URL/intervalo, red abierta, conservación de clave para el mismo SSID, rechazo de valores inválidos y persistencia simulada NVS.
- Operación de red: apagada por defecto, prueba de conexión sin subir datos, instantánea limitada, asociación/reloj/HTTPS, recuperación de fallo de asociación, olvido de red y ausencia de la clave en telemetría.
- Capacidades de AP: RSN/AKM PSK y SAE, generación anunciada y límites/truncamiento de IE.
- Backend: **10 pruebas** con DynamoDB simulado, validación, prefijo específico, alias, reintento idempotente, GET/POST, WPS, almacenamiento BLE separado y aceptación del JSON generado por el código real del snapshot V7.1 en la prueba nativa.
- Panel en DOM simulado: compatibilidad V7 y V7.1, conteos, filtros, detalles, prevención de interpretación de HTML recibido, estados de capacidad y telemetría antigua, demo aislada, CSV, ensayos, descarga y UTF-8. Para la red se verifica que un mensaje periódico no borre lo que estás escribiendo, que el campo de clave se vacíe tras enviarlo, que no se guarde esa clave en localStorage, que los mensajes se muestren como texto y que una pausa de radio marque incidencia en el ensayo.

Las pruebas C++ de los cambios se ejecutaron con GCC nativo y comprobador de comportamiento indefinido. Sus sustitutos de hardware no prueban el controlador real ni el tráfico de red.

## Pendiente sobre tu placa

Carga, recepción Wi-Fi/BLE real, conexión a tu AP, certificado/cadena de tu API, despliegue Lambda, RAM libre y fragmentación durante TLS, cancelación de sockets real, duración de pausas, estabilidad prolongada, alimentación/consumo, accesorios y visualización en navegador real. No se midieron precisión de modelo, número físico real de equipos ni latencia/pérdidas sobre hardware.

No se ha hecho POST a tu API ni se ha modificado tu cuenta AWS. Las pruebas de backend emplean un doble de DynamoDB y las de HTTPS, un doble de HTTPClient. No se presenta esa simulación como envío real.

## Reproducción de pruebas de desarrollo

Los tests están en `tests/`. Para C++ nativo usa GCC y compila `tests/vendor/cJSON.c` una vez. Por ejemplo, desde la raíz del proyecto:

```bash
gcc -c tests/vendor/cJSON.c -o cjson.o
g++ -std=c++17 -O2 tests/test_network_config.cpp cjson.o -o test_network_config
./test_network_config
g++ -std=c++17 -O2 -I tests/network_stubs tests/test_network_runtime.cpp cjson.o -o test_network_runtime
./test_network_runtime tests/payload_cloud.json
python3 tests/test_cloud_backend.py
```

El test del panel requiere Node y `happy-dom`; ejecútalo con esa dependencia disponible y desde la raíz del proyecto. Para verificar el firmware usa Arduino IDE con las opciones de `EMPEZAR_AQUI.md`.

## Pruebas históricas de V7

El texto siguiente se conserva como antecedente; los tamaños y las afirmaciones de su entrega corresponden a V7, no a V7.1.

# Verificación V7.0

## Compilación y enlace para el ESP32

Firmware completo compilado con Arduino-ESP32 **3.3.2**, ESP32 Dev Module clásico, flash de 4 MB y partición **Huge APP**:

- Programa: **2 805 691 / 3 145 728 bytes (89 %)**.
- Variables globales: **99 776 / 327 680 bytes (30 %)**.
- El resto de RAM no equivale a heap libre garantizado en ejecución: el controlador Wi-Fi/BLE, colas y pilas también solicitan memoria. El panel muestra heap actual y mínimo para la comprobación física.
- La V6 adjunta documentaba 3 052 315 bytes (97 %) en su configuración inicial. La representación compacta IEEE conserva datos y mejora el margen de programa.

Se compiló el programa completo, incluyendo OLED, RTC, recuperación BLE, watchdog, flash y comandos USB, no solo una prueba de sintaxis. No se cargó en una placa remota. La ocupación depende de la versión de core, opciones y cambios; utiliza los ajustes documentados.

## Pruebas automatizadas realizadas

| Prueba | Comprobaciones |
|---|---|
| `test_count.cpp` | Longitudes de tramas, dirección transmisora, roles, SSID, RSSI EMA, ventana de 60 s, rollover, tablas 96/32, no reemplazar filas recientes, MAC aleatoria BLE sin reglas U/L Wi-Fi, nombres e IDs contradictorios, conflicto WPS y 50.000 entradas aleatorias/malformadas |
| `test_ieee.cpp` | 54.220 prefijos y 108.399 consultas en extremos, prefijo más largo, denominaciones preservadas, exclusión de local/grupo, duplicados y 10.000 MAC aleatorias |
| `test_bluetooth_registry.cpp` | Las 4.049 denominaciones SIG coinciden con los vectores de la copia original |
| `test_hardware.cpp` | Periféricos I²C simulados: presencia opcional, OSF RTC, rangos/calendario, sincronización UTC, software clock, límites del buffer OLED y recuperación tras fallo de bus |
| `test_journal.cpp` | Módulo real de registro con flash/UART simulados: montaje sin reformato destructivo, CSV 16 columnas, eventos/resúmenes, rotación, instantánea y bloques UTF-8, contrapresión y comandos acotados |
| `test_ui.mjs` | HTML real con Happy DOM: conteos separados, filtros/detalles, escape de HTML, capacidad/datos antiguos, estabilización y estadística de ensayos, cancelación al reiniciar, secuencias de descarga, UTF-8 y demostración aislada |

Las pruebas C++ se ejecutaron con UndefinedBehaviorSanitizer. Los periféricos simulados no validan el cableado real, niveles eléctricos ni tiempos de bus. Se intentó una inspección visual con Chromium local, pero el navegador no pudo arrancar en este entorno; por ello **no se afirma una verificación visual renderizada completa**. La lógica de la interfaz sí pasó las pruebas DOM; conviene revisar su presentación en Chrome/Edge de tu PC.

## Reproducir lógica en un PC de desarrollo

Desde la carpeta extraída, con g++/gcc:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -fsanitize=undefined tests/test_count.cpp -o test_count
./test_count
g++ -std=c++17 -O2 -Wall -Wextra -Werror -fsanitize=undefined tests/test_ieee.cpp -o test_ieee
./test_ieee data/expected_assignments.tsv
g++ -std=c++17 -O2 -Wall -Wextra -Werror -fsanitize=undefined tests/test_bluetooth_registry.cpp -o test_bluetooth_registry
./test_bluetooth_registry tests/bluetooth_vectors.tsv
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -fsanitize=undefined tests/test_hardware.cpp -o test_hardware
./test_hardware
gcc -c tests/vendor/cJSON.c -o cjson.o
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -fsanitize=undefined tests/test_journal.cpp cjson.o -o test_journal
./test_journal
```

Para la interfaz, Node.js y `happy-dom` son dependencias **solo de desarrollo**:

```sh
npm install --no-save happy-dom
node tests/test_ui.mjs
```

No necesitas estas herramientas para cargar el firmware con Arduino IDE ni para usar la página HTML.

## Pendiente sobre tu placa

Prueba de alimentación independiente y retención, estabilidad prolongada/heap, recepción Wi-Fi/BLE real, fases de radio, saturación, recuperación por fallos, funcionamiento de LED/OLED/RTC y ensayos con cantidades conocidas. No se han medido consumo, alcance, precisión física de conteo, detección universal ni garantía de marca/modelo exactos. La campaña de latencia, colas y pérdidas queda para la fase posterior.
