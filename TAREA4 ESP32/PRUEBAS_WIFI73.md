# Verificaciones de la entrega 7.3

- Compilación real Arduino CLI para espressif:esp32:esp32, core 3.3.2, partición Huge APP: correcta. Flash 2 184 723 bytes (69%); globales 96 000 bytes (29%). La CLI informó ausencia de herramientas de descubrimiento USB en el entorno; no impidió compilar. No se realizó carga física.
- C++: parser de huellas con TLV truncado y desbordamiento; exclusión del contenido SSID; sensibilidad a capacidades; conservación de huella al recibir tramas de datos; conteo de probes y suavizado RSSI.
- C++: clasificación WPS/P2P, nombres, conflictos y ausencia de inferencia desde SSID/fabricante.
- Python: 17 pruebas de API/puente USB (autenticación, persistencia, reinicios, sensor desconectado, orden temporal, límites, rechazo BLE, ida/vuelta de huella y catálogo).
- Python: 2 pruebas de entrenamiento con datos sintéticos explícitos; rechazo de fuga entre conjuntos, candidatos ambiguos, desconocidos y soporte insuficiente. Los datos sintéticos NO se incorporan al catálogo.
- JavaScript con happy-dom: envío USB→API, consulta remota, tokens, ausencia de bucle, conexión caducada, controles Wi-Fi, distancia a 1 m, parámetros inválidos, detalles y rechazo de huella incompleta.
- No se verificó visualmente en un navegador real: el entorno no tenía Chromium instalado. No se verificó con una placa física ni con mediciones de radio. No hay métricas reales de precisión de clasificación o distancia.

Desde la carpeta principal, en un entorno de desarrollo con compilador C++ y Python:

```bash
g++ -std=c++17 tests/test_wifi73.cpp -o /tmp/test_wifi73
/tmp/test_wifi73
g++ -std=c++17 tests/test_classifier.cpp -o /tmp/test_classifier73
/tmp/test_classifier73
python3 -m pip install -r servidor/requirements.txt -r herramientas/requirements.txt
python3 tests/test_ec2.py
python3 tests/test_training73.py
npm install --no-save happy-dom
node tests/test_ec2_ui.mjs
```

El directorio investigacion/historico contiene documentación y pruebas de versiones anteriores; no forma parte de la batería actual.
