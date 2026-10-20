# Fuentes primarias y procedencia

- ESP32 clásico, documentación de radio y memoria: https://documentation.espressif.com/esp32_datasheet_en.html
- Arduino-ESP32 3.3.2, código y bibliotecas usadas: https://github.com/espressif/arduino-esp32/tree/3.3.2
- ESP-IDF 5.5, coexistencia Wi-Fi/BLE y radio compartida: https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-guides/coexist.html
- ESP-IDF 5.5, watchdog, suscripción y reinicio: https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/system/wdts.html
- Analog Devices / Maxim, DS3231, I²C, registros BCD, estado OSF, respaldo y funcionamiento a 3,3 V: https://www.analog.com/media/en/technical-documentation/data-sheets/ds3231.pdf
- Solomon Systech, SSD1306, comandos y memoria gráfica; copia del datasheet alojada por Adafruit: https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf
- Adafruit, OLEDs y direcciones dependientes del módulo: https://learn.adafruit.com/monochrome-oled-breakouts/wiring-128x64-oleds
- IEEE, datos públicos MA-L/MA-M/MA-S: https://standards-oui.ieee.org/oui/oui.csv ; https://standards-oui.ieee.org/oui28/mam.csv ; https://standards-oui.ieee.org/oui36/oui36.csv
- La copia IEEE se heredó del ZIP V6 adjunto: fecha de snapshot 2026-10-19; fuentes/hashes en `data/ieee_manifest.json`. La compactación V7 es reversible; `tests/test_ieee.cpp` compara 54.220 asignaciones y límites. No se afirma que sea una descarga nueva de hoy.
- Bluetooth SIG, Assigned Numbers: https://www.bluetooth.com/specifications/assigned-numbers/ ; YAML oficial enlazado: https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers/company_identifiers/company_identifiers.yaml
- La copia SIG se heredó del ZIP V6: 4.049 entradas, procedencia/hash en `data/bluetooth_companies.json`; `tests/test_bluetooth_registry.cpp` verifica las denominaciones. No identifica por sí misma el fabricante del producto.
- Arm, diseño de sistemas embebidos, función dedicada y restricciones: https://www.arm.com/glossary/embedded-system-design

Los manuales de los chips no validan automáticamente una placa de desarrollo, módulo OLED/RTC o batería concretos. Se necesita contrastar el montaje físico del usuario. La entrega incluye pruebas de software, no mediciones físicas de alcance, consumo ni precisión universal del conteo.


## Integración V7.1

- Espressif, Preferences/NVS: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/preferences.html
- Espressif, modos Wi-Fi y restricciones de canal/conexión: https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi-driver/wifi-modes.html
- Código Arduino-ESP32 3.3.2, HTTPClient: https://github.com/espressif/arduino-esp32/tree/3.3.2/libraries/HTTPClient
- Amazon Trust Services, repositorio de certificados raíz: https://www.amazontrust.com/repository/

Los tres adjuntos de código aportados por el usuario se usan como fuente de integración, no como referencias científicas. La base IEEE/SIG se conserva del ZIP V7 adjunto; no se atribuye a una descarga nueva.


## Clasificación V7.2

- Bluetooth SIG, Assigned Numbers: valores Appearance (Phone 0x0040, Laptop 0x0083, Tablet 0x0087, Television 0x0A01, Projector 0x0A03): https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Assigned_Numbers/out/en/index-en.html
- Bluetooth Core, GAP: Appearance es una representación anunciada del equipo: https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/host/generic-access-profile.html
- Implementación primaria wpa_supplicant/hostapd, categorías y subcategorías WPS/Wi-Fi Direct, WFA OUI 0x0050F204: https://w1.fi/wpa_supplicant/devel/wps__defs_8h_source.html

Las reglas por palabras en nombres son reglas propias y no una tabla oficial de identificación. Los códigos anunciados no autentican el aparato y no prueban marca/modelo.


## Integración de página y API en EC2

- AWS EC2, reglas de grupo de seguridad para servidores web: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html
- MDN, Web Serial: puerto del equipo anfitrión y requisito de contexto seguro: https://developer.mozilla.org/en-US/docs/Web/API/SerialPort
- Flask, despliegue con Gunicorn: https://flask.palletsprojects.com/en/stable/deploying/gunicorn/
- Docker, instalación en Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Caddy, HTTPS automático: https://caddyserver.com/docs/automatic-https
- PyPI: Flask 3.1.3, Gunicorn 26.2.0 y pyserial 3.5, versiones verificadas mediante la API oficial de PyPI al preparar esta entrega.

Se inspeccionó el repositorio público AxelVZM/SISTEMASEMBEBIDOS para preparar una carpeta independiente y conservar las tareas existentes. La guía de TAREA2 declara Ubuntu/PM2/Nginx; no se ha comprobado que esa configuración sea la que corre actualmente en EC2.
