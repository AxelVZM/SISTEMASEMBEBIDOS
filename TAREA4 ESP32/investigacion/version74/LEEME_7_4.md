# Órbita 7.4 — Wi-Fi, BLE manual y red local

Esta entrega aún no está instalada en tu EC2 ni en la placa. Consulta ACTUALIZAR_7_4.md.

- Wi-Fi empieza automáticamente al alimentar/reiniciar el ESP32.
- Abrir el apartado Bluetooth no activa nada. Pulsa Activar detección BLE para dedicar la escucha a anuncios BLE. Desactivar BLE y volver a Wi-Fi detiene BLE y reanuda el salto de canales Wi-Fi.
- BLE no se activa por intervalos ni se guarda como modo de arranque. Si cierras el navegador tras activarlo, la placa conserva ese modo hasta desactivarlo o reiniciarla. El controlador Bluetooth se inicializa bajo demanda y puede quedar inicializado pero sin escanear al volver a Wi-Fi.
- La nueva sección Red local permite configurar una red y pulsar Conectar y buscar servicios. La placa conecta a esa red, consulta cinco clases de servicios mDNS y después desconecta y vuelve a Wi-Fi pasivo. No se mantiene una asociación permanente ni se consulta el router para listar sus clientes.
- La interfaz separa direcciones Wi-Fi, direcciones BLE y servicios LAN. No suma esos números ni une identidades entre protocolos.

## Qué se puede identificar
Wi-Fi: titular IEEE de una MAC universal y datos declarados por WPS/P2P. Una MAC local/aleatoria no permite atribuir fabricante por OUI. Tampoco una MAC universal prueba el modelo comercial.

BLE: determinados anuncios Apple proximity pairing y MiBeacon FE95 permiten mostrar un modelo anunciado. Company ID y modelo son evidencias distintas. Los códigos desconocidos o contradictorios quedan sin modelo. Los anuncios pueden ser falsificados: no se autentica identidad.

LAN: nombre, host, IPv4, servicio, puerto y campos de marca/modelo si existen en el TXT mDNS. “Modelo” puede ser una denominación técnica o descripción declarada. No se promete identificar cada dispositivo. No se infiere marca por el nombre del servicio ni por el nombre del equipo.

No se instaló el catálogo experimental de huellas Wi-Fi de la evaluación anterior. Sigue vacío, porque la prueba con unidades no vistas no justificó habilitarlo.

## Alcance de la placa
ESP32 clásico, Arduino-ESP32 3.3.2, partición Huge APP. Wi-Fi 2,4 GHz, canales 1–11. BLE pasivo con anuncios legacy de hasta 31 bytes; no incluye Bluetooth Classic, publicidad extendida BLE 5, emparejamiento ni lectura GATT.

Los controles requieren USB local con firmware 7.4. La consulta remota sirve para observar resultados y exportarlos, no para activar radios. El enlace USB→EC2 transporta Wi-Fi, BLE y LAN. La subida directa opcional antigua a Lambda mantiene su alcance Wi-Fi previo.

Lee investigacion/BASE_TECNICA_7_4.md para las fuentes, identificadores y pruebas. Los documentos en version73 e historico describen versiones anteriores.
