# Atribución V7

Los prefijos IEEE y nombres de titulares proceden del registro público oficial; fuentes y hashes en data/ieee_manifest.json. V7 conserva la copia V6 sin pérdida, compactando nombres y entradas.

Company Identifiers: registro público Bluetooth SIG, fuente/hash en data/bluetooth_companies.json. Los titulares y marcas pertenecen a sus respectivos propietarios; no se implica certificación ni aprobación de SIG o IEEE.

El firmware usa Arduino-ESP32 y ESP-IDF mediante el paquete oficial Espressif; no incorpora sus bibliotecas como binarios dentro de este ZIP. Wire, WiFi, LittleFS y Preferences forman parte de ese paquete.

Las pruebas incluyen cJSON, copyright Dave Gamble y colaboradores, bajo licencia MIT; el aviso completo está en tests/vendor/cJSON.c y cJSON.h. El firmware enlaza el cJSON incluido por Espressif.

Las referencias de entrenamiento, clasificadores y conjuntos de sondeos de V6 se retiraron y no se utilizan en V7. No se distribuyen aquí los datasets de captura.

V7.4: mapeos de producto contrastados con Theengs Decoder y ESPHome. Implementación propia del parser; enlaces y hashes de las referencias consultadas en investigacion/BASE_TECNICA_7_4.md y referencias_decoders_sha256.json. No se distribuyen los archivos fuente externos de esas consultas.

## Extensión 7.5
Las nuevas tablas y parsers fueron implementados para este proyecto a partir de las especificaciones y asociaciones documentadas en investigacion/BASE_TECNICA_7_5.md. Se conserva la atribución previa a ESPHome/Theengs. Ruuvi RAWv2 se reconoce según su especificación pública; no se incorpora su biblioteca ni se atribuye un modelo exacto.
