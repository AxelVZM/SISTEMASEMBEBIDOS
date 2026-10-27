# Verificación 7.5

## Resultado ejecutado
- Compilación y enlace completos con Arduino-ESP32 3.3.2, ESP32 Dev Module clásico, Huge APP: correctos.
- Flash: 3.015.827 / 3.145.728 bytes (95 %); quedan 129.901 bytes.
- Variables globales: 116.820 / 327.680 bytes (35 %). No equivale al heap libre real después de activar radios, TLS y búsqueda LAN.
- Cinco ejecutables C++ correctos: huellas Wi-Fi, clasificación WPS/P2P, BLE/TXT, control de modos y nuevas reglas/SSDP/XML.
- Nuevas pruebas: equivalencias de fabricante/código, fabricante incompatible, URL local/remitente, rechazo de URLs ajenas/credenciales/inyección, cabeceras duplicadas, XML truncado en cada posición, DTD/entidades desconocidas, no mezclar dispositivos hijos, conflictos TXT, roles LAN, diez IDs MiBeacon añadidos y formato Ruuvi sin atribución de modelo.
- API/puente: 19 pruebas Python correctas, incluidas persistencia de modelo/tipo LAN, estado 7.5, límites de campos y rechazo de clasificaciones inválidas.
- Dos pruebas de interfaz/transportes con happy-dom correctas: activación BLE explícita, navegación sin activar, exclusión BLE/LAN, retorno, borrado de búsqueda anterior, campos escapados, nuevo tipo/código/modelo LAN, publicación USB, token y vista remota de solo lectura.

La compilación de este entorno usó el compilador GCC Xtensa subyacente del mismo paquete y la configuración xtensa_esp32.so, porque el lanzador de Espressif necesita /proc/self/exe, que aquí no está disponible. El código del proyecto y las bibliotecas no se modificaron para sortearlo. En Arduino IDE normal se usa el paquete estándar sin ese ajuste.

## No ejecutado
No hay prueba con una placa, AirPods, sensores o router físico. No se ha medido precisión, cobertura, consumo, heap con radios activas ni estabilidad prolongada. No se ha entrenado un modelo de ML nuevo. La interfaz se verificó por DOM y comportamiento, sin evaluación visual en un navegador real. No se ha actualizado GitHub, EC2 ni el firmware de tu placa.

## Repetir
Desde ESP32_EC2 con g++, gcc, Python y Node instalados:

```bash
g++ -std=c++17 tests/test_wifi73.cpp -o test_wifi
./test_wifi
g++ -std=c++17 tests/test_classifier.cpp -o test_classifier
./test_classifier
g++ -std=c++17 tests/test_ble_models.cpp -o test_ble
./test_ble
g++ -std=c++17 tests/test_discovery75.cpp -o test_discovery
./test_discovery
gcc -c tests/vendor/cJSON.c -o cjson.o
g++ -std=c++17 tests/test_mode_control.cpp cjson.o -o test_modes
./test_modes
python3 -m pip install -r servidor/requirements.txt -r herramientas/requirements.txt
python3 tests/test_ec2.py
npm install --no-save happy-dom
node tests/test_modes.mjs
node tests/test_ec2_ui.mjs
arduino-cli compile --fqbn esp32:esp32:esp32:PartitionScheme=huge_app DetectorTiempoReal
```

Realiza las comprobaciones físicas de ACTUALIZAR_7_5.md antes de usar resultados como evidencia experimental.
