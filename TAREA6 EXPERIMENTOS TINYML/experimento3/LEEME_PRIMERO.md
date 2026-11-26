# EXPERIMENTO 3 — ESP32-CAM / TinyML / LED rojo y blanco integrado / USB HTML

**Correcciones:** usar también el LED rojo integrado de GPIO33 cuando el izquierdo detecta obstáculo; conservar el LED blanco integrado GPIO4 para obstáculos del lado derecho; recibir lecturas USB continuas en el HTML mediante Web Serial; incorporar diagnóstico y compatibilidad con texto del Monitor Serie; reemplazar la dependencia que fallaba `tflm_esp32` por inferencia numérica de pesos entrenados.

## 1. Circuito: NO se modifica

| Elemento | Pin ESP32-CAM | Observación |
|---|---|---|
| Sensor izquierdo TRIG / ECHO | IO13 / IO14 | ECHO protegido por divisor 1 kΩ + 2 kΩ hacia GND |
| Sensor derecho TRIG / ECHO | IO15 / IO2 | ECHO protegido por divisor 1 kΩ + 2 kΩ hacia GND |
| VCC de ambos sensores | 5V | Tierra común GND |
| LED externo izquierdo | IO12 | Resistencia 220 Ω en serie |
| LED externo derecho | IO4 | Resistencia 220 Ω en serie |
| LED rojo **integrado** | IO33 | Control interno, activo LOW. Sin cables |
| Flash LED blanco **integrado** | IO4 | Comparte pin con LED externo derecho. Sin cables |

**Sin cámara activa, sin Wi-Fi, sin microSD, sin LEDs nuevos.** Nunca insertar dos patas/cables en el mismo agujero de protoboard. El flash blanco es potente: no mirarlo directamente ni dejarlo encendido innecesariamente.

## 2. Lo que hay que hacer para que funcione YA

1. Abre `Arduino/01_Prueba_Sensores_LEDs/01_Prueba_Sensores_LEDs.ino` en Arduino IDE y selecciona **AI Thinker ESP32-CAM**.
2. Sube el sketch. Si aparece `Wrong boot mode (0xb)`: desconecta el USB, IO0 a GND solo para cargar; si necesario retira temporalmente IO2, y después de cargar quita IO0-GND y repón IO2 con el USB desconectado. En ejecución normal **IO0 NO debe estar unido a GND**.
3. Comprueba en Monitor Serie a **115200** que llegan líneas JSON que empiezan con `{"izquierda_cm":...}`. Con el izquierdo a menos de 20 cm se encenderán el LED externo IO12 y el rojo integrado IO33; con el derecho se encenderán el LED externo IO4 y el blanco de la cámara.
4. **CIERRA EL MONITOR SERIE**, ya que Windows no permite que el monitor y el navegador abran el mismo COM simultáneamente.
5. Haz doble clic en **`Panel_HTML/abrir_local.cmd`**. Se abre una ventana de PowerShell (mantener abierta) y el panel en **http://127.0.0.1:18763/**. Necesitas Chrome o Edge de escritorio.
6. Pulsa **Conectar ESP32-CAM (elegir COM)**, elige el COM que Windows muestre para ESP32-CAM-MB (COM9, COM10 u otro). Se leerán líneas continuamente, SIN Python ni puentes COM.
7. Si falta data: lee *Diagnóstico de conexión USB*; muestra si llegan bytes, líneas, o si el puerto está abierto sin datos. Se pueden exportar las mediciones reales a CSV.

**Importante:** el `.cmd` emplea PowerShell instalado con Windows para SERVIR EL HTML en `localhost` de manera segura. No lee el COM. El navegador conecta al USB directamente mediante la API Web Serial. Este servidor local NO requiere internet ni Python.

## 3. Programa TinyML — dos opciones

- **Prueba inicial:** `01_Prueba_Sensores_LEDs.ino` usa reglas para confirmar que funcionan sensores, rojo, blanco y HTML, **NO es TinyML**.
- **Versión neuronal:** `02_TinyML_Sensores_LEDs.ino` ejecuta una red neuronal real `2 → 24 → 16 → 4` (Dense ReLU, Softmax) dentro del microcontrolador. En su carpeta se incluye un `model.h` preentrenado con 8,000 muestras SINTÉTICAS, para probar directamente.

El nuevo sketch **NO requiere** las bibliotecas `tflm_esp32` ni `EloquentTinyML`: no habrá el fallo anterior de definiciones duplicadas de ellas. Usa las matrices entrenadas de `model.h` directamente en C++.

Si quieres entrenar de cero: abre `Colab/Entrenamiento_Obstaculos_TinyML_ESP32CAM.ipynb` en Google Colab, elige **Ejecutar todas**, extrae el `model.h` obtenido del ZIP `Modelo_TinyML_Para_Arduino.zip` y reemplaza el `model.h` preentrenado que está junto al sketch `02_TinyML_Sensores_LEDs.ino`. El notebook también exporta `.tflite` para documentación y verifica la equivalencia numérica del modelo con la inferencia calculada por matrices.

**No sirve el `model.h` antiguo** que contenía únicamente bytes `.tflite` con la versión nueva del sketch: utiliza el que viene en esta entrega o vuelve a generar el actualizado con el Colab.

## 4. Qué muestra el panel

- Distancias izquierda y derecha actualizadas automáticamente aproximadamente cada 350–400 ms mientras el dispositivo sigue transmitiendo.
- Estado de los LEDs, dirección recomendada, confianza en modo TinyML, gráfico continuo, historial y exportación a CSV.
- **Diagnóstico**: bytes recibidos, líneas recibidas, hora de la última medición y última línea recibida. Soporta JSON actual y, para lecturas, texto antiguo `IZQUIERDA: ... | DERECHA: ...`.
- Si el firmware es el sketch 01, el panel indica **REGLAS_PRUEBA** y confianza no disponible. En el sketch 02, indica **TINYML** con confianza numérica.

## 5. Limitaciones y comprobación

- Los 8,000 registros son **sintéticos**, no datos medidos en el circuito. El archivo `Datos/validacion_modelo_preentrenado.txt` documenta la evaluación en datos de prueba sintéticos, **no** garantiza precisión en entornos reales.
- Dos sensores laterales no detectan necesariamente obstáculos frontales fuera de sus haces; **no controlar robots móviles reales** con este circuito sin una validación adicional.
- En ESP32-CAM AI-Thinker el pequeño LED rojo GPIO33 se activa con `LOW`. Algunas placas clones pueden tener un LED distinto o carecer de él; el LED externo izquierdo IO12 permanece funcionando.
- El LED blanco GPIO4 también se activa con el LED externo derecho y puede calentarse si permanece encendido.
- La comunicación real con el ESP32-CAM físico depende de Windows, drivers CH340, COM libre y permisos del navegador. En este paquete se revisaron los archivos y el procesamiento del HTML, pero no se pudo realizar una prueba física en tu hardware.
