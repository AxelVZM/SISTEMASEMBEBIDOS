# Verificación 7.4

## Ejecutado
- Compilación real Arduino CLI con Arduino-ESP32 3.3.2, ESP32 Dev Module y Huge APP: correcta. Flash 2.998.855 bytes, 95 % de 3.145.728. Variables globales 116.500 bytes, 35 %. El descubrimiento USB del entorno emitió avisos; la compilación final terminó con código 0.
- Cuatro ejecutables C++: regresión de huellas Wi-Fi; clasificación WPS/P2P; decodificación BLE y TXT LAN; control de modos.
- Control de modos con APIs simuladas: Wi-Fi por defecto sin inicializar BLE; activación bajo comando; activación repetida no reinicializa; desactivación espera confirmación de parada; comandos bloqueados durante red/descarga; rechazo de valor no booleano; fallo de inicio BLE permite volver a Wi-Fi.
- Decodificadores: nueve IDs Apple/Beats, ID MiBeacon LYWSD03MMC con flag de cifrado, fabricante incorrecto, ID desconocido, TLV truncados, campos opcionales incompletos y contradicción de modelo. Las tres entradas MiBeacon se revisaron contra su tabla de referencia. Los vectores son sintéticos derivados de los formatos, NO capturas de dispositivos reales.
- API y puente: 18 pruebas Python. Incluyen autenticación, datos persistentes, reinicios, límites, Wi-Fi/huellas, BLE/modelo, LAN/modelo, nueva búsqueda retirando datos anteriores y rechazo de banderas inválidas.
- Interfaz con happy-dom: navegación no activa BLE, botones envían comandos explícitos, exclusión BLE/LAN, campos escapados contra HTML, cambio de búsqueda limpia filas y control remoto de solo lectura.

## No verificado
No hubo placa, AirPods ni sensores físicos conectados. No hay porcentaje medido de reconocimiento ni de cobertura. No se probó mDNS contra un router físico ni el consumo real de heap tras inicializar Bluetooth. La partición Huge APP es necesaria y queda aproximadamente un 5 % de flash disponible.

Se intentó iniciar un navegador para revisión visual, pero no había Chromium y su descarga no produjo un archivo utilizable. La interfaz se verificó por su DOM/comportamiento, no mediante captura visual en un navegador real. La validación física y visual en el equipo del usuario sigue pendiente.

## Repetir pruebas
Desde la carpeta principal, con un compilador C++17, Node y Python:

```bash
g++ -std=c++17 tests/test_wifi73.cpp -o /tmp/test_wifi
/tmp/test_wifi
g++ -std=c++17 tests/test_classifier.cpp -o /tmp/test_classifier
/tmp/test_classifier
g++ -std=c++17 tests/test_ble_models.cpp -o /tmp/test_ble_models
/tmp/test_ble_models
gcc -c tests/vendor/cJSON.c -o /tmp/cjson.o
g++ -std=c++17 tests/test_mode_control.cpp /tmp/cjson.o -o /tmp/test_modes
/tmp/test_modes
python3 -m pip install -r servidor/requirements.txt -r herramientas/requirements.txt
python3 tests/test_ec2.py
npm install --no-save happy-dom
node tests/test_modes.mjs
```

La compilación de firmware requiere el paquete Espressif 3.3.2, placa ESP32 clásico y partición Huge APP. Las herramientas/simulaciones host no sustituyen las pruebas de radio.
