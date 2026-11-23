# Reparación del puerto dinámico ESP32-CAM

## Qué estaba mal
El HTML indicaba COM10 incluso al abrir otro puerto. El puente Windows también usaba `--port COM10` fijo. Ambos se corrigieron.

## Importante
El navegador usa el selector nativo Web Serial, por lo que permite elegir cualquier COM. Si muestra «USB abierto · Bytes: 0», **el número COM no es la causa directa**: el puerto fue abierto, pero todavía no envía datos. Primero pulsa RST en la base MB y confirma en Arduino Monitor Serie a 115200 que existan líneas `CAL,` o `TINYML,`.

## Instalar
Reemplaza `05_AWS/index.html` y `06_PUENTE_WINDOWS/puente_usb_aws.py` e `iniciar_puente.cmd` en GitHub.
En la consola web de AWS: `cd /home/ubuntu/SISTEMASEMBEBIDOS && git pull origin main && sudo systemctl restart experimento2-tinyml`.
En Chrome/Edge actualiza con Ctrl+Shift+R.

## Dos formas de lectura (usar solo una a la vez)
- **Navegador:** Conectar ESP32-CAM y elegir USB-SERIAL CH340 en cualquier puerto COM. No hay número fijo.
- **Puente:** en Windows abrir `iniciar_puente.cmd`. Detecta CH340/CP210x cuando hay uno, o pide elegir si hay varios. No requiere un COM fijo. Antes, desconectar Web Serial y cerrar el Monitor Serie.

## Diagnóstico
- Bytes 0: comprueba RST, alimentación, programa cargado, puerto correcto y Monitor Serie a 115200.
- Bytes > 0 y válidas 0: revisar Última línea; firmware puede no enviar CAL/TINYML.
- Válidas > 0 pero AWS 0: error HTTPS o API mostrado en el panel.
- Para Arduino la ESP32-CAM debe enviar cada ~2.5 s una línea `CAL,23.4,45.6,...` si fue cargado `TinyML_Calibrado.ino`.

No abrir nunca dos aplicaciones simultáneas sobre el mismo puerto.
