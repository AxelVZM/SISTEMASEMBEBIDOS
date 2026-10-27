# Base técnica, evidencia y límites de Órbita 7.4

## Fuentes y decisiones
1. Espressif, RF Coexistence: ESP32 comparte recursos RF entre Wi-Fi y Bluetooth; usa división temporal. Implementamos selección excluyente de captura, con Wi-Fi por defecto y BLE bajo orden USB. No se promete escucha simultánea completa.
   https://docs.espressif.com/projects/esp-idf/en/v5.5-rc1/esp32/api-guides/coexist.html
2. Bluetooth SIG, Assigned Numbers y Company ID Questions: el Company Identifier identifica al titular del código de datos de fabricante, no un modelo universal ni una marca comercial garantizada.
   https://www.bluetooth.com/specifications/assigned-numbers/
   https://support.bluetooth.com/hc/en-us/articles/19287261092109-Company-ID-Questions
3. Theengs Decoder, APPLEAIRPODS_json.h: referencia abierta del formato Apple proximity pairing, filtro y tabla de identificadores. La implementación aquí es propia, limitada al anuncio validado; no utiliza funciones IRK ni vincula MAC rotatorias.
   https://github.com/theengs/decoder/blob/development/src/devices/APPLEAIRPODS_json.h
4. ESPHome, xiaomi_ble.cpp: referencia del encabezado MiBeacon FE95 y sus IDs de producto. Se lee solo el identificador de producto; no se descifran mediciones ni se solicitan claves.
   https://github.com/esphome/esphome/blob/dev/esphome/components/xiaomi_ble/xiaomi_ble.cpp
   https://esphome.io/components/sensor/xiaomi_ble/
5. RFC 6763, DNS-Based Service Discovery: PTR/SRV/TXT permiten descubrir servicios y metadatos. Se consultan _device-info._tcp, _airplay._tcp, _googlecast._tcp, _ipp._tcp y _http._tcp; máximo 24 resultados y ocho por consulta. Solo se muestran brand/manufacturer/usb_MFG y model/md/ty/usb_MDL cuando vienen declarados. No se deduce modelo del nombre ni de la IP. No se enumeran todos los clientes del router.
   https://www.rfc-editor.org/rfc/rfc6763
6. Investigación de 2024: *A device identification method from BLE advertising packets with randomized MAC addresses based on regression of received signal strength*, IEICE Communications Express 13(3). Distinguir una unidad a pesar de MAC cambiantes es un problema diferente de reconocer su modelo comercial. Este proyecto no implementa esa reidentificación ni traslada su rendimiento a nuestro decodificador.
   https://www.jstage.jst.go.jp/article/comex/13/3/13_2023XBL0157/_article/-char/en

La base del decodificador son formatos y tablas verificables, no un nuevo entrenamiento de IA. Las referencias científicas no demuestran que todos los dispositivos expongan modelo ni que las tablas de terceros autentiquen un producto. Los datos del proyecto anterior siguen disponibles bajo METODO_Y_ENTRENAMIENTO.md.

## Modelos incluidos
Para Apple, exige AD Manufacturer Specific Data de 29 bytes, Company ID 0x004C, tipo 0x07, longitud 0x19 y byte de versión 0x01. Se interpreta un identificador de DOS bytes, little-endian, en posiciones 5–6 contando desde el Company ID. No es un byte genérico válido para cualquier anuncio Apple.

| ID | Modelo anunciado |
|---|---|
| 0x2002 | AirPods 1.ª generación |
| 0x200F | AirPods 2.ª generación |
| 0x200E | AirPods Pro 1.ª generación |
| 0x2014 | AirPods Pro 2 Lightning |
| 0x2024 | AirPods Pro 2 USB-C |
| 0x200A | AirPods Max Lightning |
| 0x2003 | Powerbeats3 |
| 0x2005 | BeatsX |
| 0x2006 | Beats Solo3 |

Para MiBeacon, exige Service Data UUID FE95, encabezado válido, versión de formato 2–5, flag de datos y longitudes mínimas de campos opcionales. El producto está en los dos bytes siguientes al frame control. El flag de cifrado se muestra sin descifrar contenido.

| ID MiBeacon | Modelo | Atribución |
|---|---|---|
| 0x01AA | LYWSDCGQ | Ecosistema Xiaomi/Mijia |
| 0x045B | LYWSD02 | Ecosistema Xiaomi/Mijia |
| 0x055B | LYWSD03MMC | Ecosistema Xiaomi/Mijia |

Firmware alternativo ATC/PVVX puede cambiar el formato y no será reconocido por este decoder. Otros IDs conservan el código observado y “Sin determinar”. Un conflicto de IDs o Company IDs impide mostrar marca/modelo. No se adivina iPhone 14, iPad o cualquier otro equipo Apple a partir de Company ID 0x004C.

## Flujo y fiabilidad
Los campos model/brand/source/conflict se generan en la placa y pasan por USB a EC2. API con validación de tamaños/tipos conserva estas evidencias. Los resultados LAN se separan por número de búsqueda; una búsqueda nueva retira filas anteriores. El diario flash registra Wi-Fi/BLE y evidencias de producto; LAN se conserva en el snapshot de RAM y en EC2 cuando hay puente activo.

RSSI de Wi-Fi sigue mostrando distancia orientativa con parámetros ajustables. La tabla BLE solo muestra RSSI; no transfiere automáticamente la calibración Wi-Fi. Mientras Wi-Fi está pausado no se muestra distancia Wi-Fi como medida actual.

No hay precisión de campo medida para estos decodificadores. Compatibilidad de formato no garantiza que todos los equipos compatibles anuncien esos paquetes en todo estado. La detección BLE es pasiva y no obtiene scan responses mediante consultas activas. Se conservan las limitaciones de MAC privada y dispositivos silenciosos.
