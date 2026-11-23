# Experimento 2 — Reparación verificable de USB y AWS

Este paquete contiene el proyecto, una prueba de rescate independiente del modelo, un puente con impresión de datos crudos y el panel actualizado. No incluye un modelo nuevo entrenado: conserva tu firmware TinyML anterior y requiere el `model.h` de tu reentrenamiento 12/21 °C para volver a compilarlo. El dataset NO se modificó.

## ETAPA 1 (obligatoria): devolver lecturas al ESP32-CAM
1. Desconecta el USB. Verifica que ningún cable conecte GPIO0 a GND. Deja por ahora DHT22 en GPIO13 y los LEDs en GPIO14/15/2. Si falla el arranque, retira temporalmente los cables de GPIO2 y GPIO15 con la placa apagada.
2. Arduino IDE: placa AI Thinker ESP32-CAM, puerto CH340 que figure actualmente, Monitor Serie cerrado. Carga `03_ESP32_CAM/01_RESCATE_DHT22/01_RESCATE_DHT22.ino` (sin TinyML). Puede ser necesario pulsar RST al terminar la carga o durante "Connecting..." según tu base MB.
3. Abre Arduino Monitor Serie a 115200. Debe salir `BOOT,ESP32CAM_RESCATE_V1,115200`, `READY,...` y `DHT22,23.4,50.2`. Si sale `ERROR,DHT22_SIN_LECTURA`, revisa señal DATA GPIO13, 3V3, GND y pull-up del módulo. Si no hay texto, pulsa una vez RST en la base MB y revisa que GPIO0 no esté a GND.
4. Cierra el monitor serie y CIERRA la pestaña web que esté usando COM. En `06_PUENTE_WINDOWS`, haz doble clic `diagnosticar_local.cmd`: selecciona el puerto por su número; debe imprimir `[SERIAL]` y `[LECTURA]`. Esto no transmite datos a AWS.

## ETAPA 2: transmisión AWS
5. Con `diagnosticar_local.cmd` cerrado, ejecuta `06_PUENTE_WINDOWS/iniciar_puente.cmd` (puerto automático/selección). Muestra cada línea cruda y cada código HTTP AWS. No abras Web Serial al mismo tiempo.
6. La captura de rescate no genera probabilidades neuronales: aparecerá `SIN_MODELO` en el panel, lo cual es CORRECTO en esta prueba y prueba el canal completo.
7. Comprueba desde EC2: `curl -s http://127.0.0.1:18762/health`. `records` deberá aumentar después de POST 200.
8. Si Windows muestra `SSLCertVerificationError`, el certificado de tu IP no es confiable. Configura un certificado válido; para pruebas temporales en red de confianza se puede ejecutar `python puente_usb_aws.py --insecure` (no recomendado para uso habitual).

## ETAPA 3: recuperar TinyML
9. Después de ver `DHT22` local y registros en AWS, carga tu firmware `03_ESP32_CAM/TinyML_Calibrado/TinyML_Calibrado.ino` CON el `model.h` generado en el entrenamiento 12/21 °C. Comprueba `CAL,...` y probabilidades en Arduino.
10. Repite el puente. Al ver datos `CAL`, se mostrarán las probabilidades. No uses el model.h antiguo (18/27 °C).

## GitHub y EC2
Copia todos estos archivos dentro de `TAREA6 EXPERIMENTOS TINYML/experimento2`, `git add`, `git commit`, `git push`. En consola web EC2: `cd /home/ubuntu/SISTEMASEMBEBIDOS && git pull origin main && sudo systemctl restart experimento2-tinyml`. Nginx no necesita cambios.

## Interpretación sin conjeturas
- Ni BOOT ni bytes en Arduino: alimentación, arranque, cable/puerto o firmware sin ejecutar, no AWS.
- BOOT y ERROR DHT: revisar sensor y GPIO13.
- Arduino DHT pero Python 0 bytes: puerto equivocado/ocupado o estados DTR/RTS; cerrar Arduino y comprobar puerto seleccionado.
- Python [LECTURA] pero AWS 4xx: revisar API, Origin o autenticación.
- Python [LECTURA] y AWS 200, panel vacío: revisar actualización del navegador/servicio.
- DHT correcto y modelo CAL `SIN_MODELO`: problema TinyML/model.h, no conexión USB.
