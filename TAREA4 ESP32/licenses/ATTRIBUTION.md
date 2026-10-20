# Atribución V7

Los prefijos IEEE y nombres de titulares proceden del registro público oficial; fuentes y hashes en data/ieee_manifest.json. V7 conserva la copia V6 sin pérdida, compactando nombres y entradas.

Company Identifiers: registro público Bluetooth SIG, fuente/hash en data/bluetooth_companies.json. Los titulares y marcas pertenecen a sus respectivos propietarios; no se implica certificación ni aprobación de SIG o IEEE.

El firmware usa Arduino-ESP32 y ESP-IDF mediante el paquete oficial Espressif; no incorpora sus bibliotecas como binarios dentro de este ZIP. Wire, WiFi, LittleFS y Preferences forman parte de ese paquete.

Las pruebas incluyen cJSON, copyright Dave Gamble y colaboradores, bajo licencia MIT; el aviso completo está en tests/vendor/cJSON.c y cJSON.h. El firmware enlaza el cJSON incluido por Espressif.

Las referencias de entrenamiento, clasificadores y conjuntos de sondeos de V6 se retiraron y no se utilizan en V7. No se distribuyen aquí los datasets de captura.
