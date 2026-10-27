# Base técnica y límites — 7.5

Se conserva la metodología 7.4: separar observación, declaración, indicio y desconocido; conservar fuente; no identificar equipos físicos por MAC privada ni modelo por OUI. No se atribuye precisión científica sin evaluación en dispositivos reales.

## Fuentes primarias consultadas
- Arquitectura UPnP: https://upnp.org/specs/arch/UPnP-arch-DeviceArchitecture-v2.0-20140901.pdf
- Descripciones UPnP y campos de fabricante/modelo: https://learn.microsoft.com/en-us/windows/win32/upnp/creating-a-device-description
- DNS-SD: https://www.rfc-editor.org/rfc/rfc6763
- Tabla de producto MiBeacon, implementación ESPHome: https://api-docs.esphome.io/xiaomi__ble_8cpp_source
- Apple/Beats, decodificador Theengs: https://github.com/theengs/decoder/blob/development/src/devices/APPLEAIRPODS_json.h
- Ruuvi, especificación del fabricante: https://docs.ruuvi.com/communication/bluetooth-advertisements/data-format-5-rawv2
- Samsung SM-S911B: https://www.samsung.com/pe/support/model/SM-S911BZELLTP/
- Samsung variante SM-S911B/DS: https://www.samsung.com/latin/support/model/SM-S911BZGJGTO/
- Honor BVL-N49: https://www.honor.com/latam/support/phones/honor-magic6-pro/
- Honor FNE-NX9: https://www.honor.com/pe/support/phones/honor-70/

## Catálogos y niveles
MiBeacon añade 0098 HHCCJCY01; 015d HHCCPOT002; 02df JQJCY01YM; 0347 y 0b48 CGG1; 03bc GCLS002; 0576 CGD1; 066f CGDK2; 2542 LYWSD02MMC; 1203 XMWSDJ04MMC. Se mantienen 01aa LYWSDCGQ, 045b LYWSD02 y 055b LYWSD03MMC. Solo se usa la cabecera: no se descifran mediciones. Algunos productos son del ecosistema Xiaomi y no de esa marca comercial; Qingping/Cleargrass y VegTrug tienen etiquetas separadas.

Ruuvi requiere AD de fabricante 0x0499, longitud de 26 bytes y formato 5. Identifica el protocolo de telemetría, no Tag/Pro ni identidad del transmisor. Se conserva el modelo vacío. No se usa la MAC embebida para enlazar identidades.

Los cuatro códigos Samsung/Honor son coincidencias completas en campos de modelo. No se infiere un Galaxy por «Samsung» ni un iPhone por «Apple». Cualquier fabricante explícito incompatible impide aplicar la equivalencia. Los identificadores son declaraciones, no prueba de autenticidad.

Los tipos por nombres son indicios y pueden fallar. Se retiró «redmi» como regla genérica de celular porque puede nombrar tablets. Un servicio de impresión se etiqueta como rol: puede ser un servidor intermediario. MediaRenderer se conserva como multimedia y no se fuerza a televisor. El tipo de cámara sigue dependiendo de WPS/P2P o indicios; no se añadió escaneo de puertos ni ONVIF.

## Diseño embebido
Máximos: 96 registros Wi-Fi, 32 BLE y 24 servicios/descripciones LAN. La tabla LAN se reserva al solicitarla; SSDP guarda hasta 6 destinos, datagramas de hasta 1023 bytes y XML de hasta 8192 bytes en heap. Se comprueba heap antes de iniciar el trabajador y SSDP. El trabajador LAN tiene stack de 8192 bytes. Las consultas mDNS son secuenciales, con 1200 ms y 8 resultados por servicio. SSDP escucha 2200 ms; HTTP usa plazos de conexión/lectura y una ventana de lectura de cuerpo de 1200 ms. No son garantías de tiempo real duro frente a cualquier servidor defectuoso.

SSDP solo sigue URLs http con IPv4 literal igual al remitente y en la misma subred. Excluye la propia placa, direcciones de red/broadcast, loopback, multicast, credenciales, redirecciones y caracteres de control. XML restringido: máximo 16 niveles, sin DTD ni entidades externas; solo campos del dispositivo raíz, sin mezclar dispositivos hijos. Acepta entidades XML básicas. No admite XML con prefijos en etiquetas, CDATA, descripciones mayores de 8 KiB, cuerpos sin Content-Length ni codificación chunked. Esos resultados se omiten.

El bucle de captura, watchdog y manejo serie continúa durante el trabajador; la escucha Wi-Fi se pausa durante asociación/descubrimiento. BLE y LAN se excluyen. Al terminar vuelve la captura. Los registros LAN se escriben desde el hilo principal tras finalizar el trabajador, evitando acceso concurrente a LittleFS.

## Pendiente de validación física
Comparar dispositivos conocidos, sus códigos anunciados, tipos y marcas; probar equipos silenciosos/desconocidos; alternar BLE/Wi-Fi repetidamente; medir heap después de activar BLE y buscar LAN; comprobar 24 resultados, errores de red, watchdog, pérdidas de paquetes y reinicios. Medir por separado precisión de tipo, marca y modelo y cobertura; no presentar «100 %» por pasar pruebas unitarias.
