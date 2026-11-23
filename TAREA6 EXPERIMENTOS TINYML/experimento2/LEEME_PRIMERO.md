# EXPERIMENTO 2 — Umbrales corregidos: 12 °C y 21 °C

## Clasificación válida
- FRIO: T < 12 °C (LED azul / IO14)
- TEMPLADO: 12 °C <= T < 21 °C (LED verde / IO15)
- CALIENTE: T >= 21 °C (LED rojo / IO2)

## Dataset único
`02_DATASET/temperatura_humedad_calibracion.csv`: 6900 filas, etiquetas recalculadas con los límites correctos. Se preservan los campos `origen` (REAL y SINTETICO) y `sesion`.

### Distribución ACTUAL
- REAL / CALIENTE: 1000
- REAL / TEMPLADO: 2000
- SINTETICO / CALIENTE: 2128
- SINTETICO / FRIO: 570
- SINTETICO / TEMPLADO: 1202

**ADVERTENCIA:** No existen mediciones reales FRIO (< 12 °C) dentro de este archivo. Los registros REALES previamente clasificados FRIO (12.1 a 13.3 °C) ahora son TEMPLADO. Los ejemplos de FRIO son únicamente SINTÉTICOS. No se puede afirmar que se haya demostrado la precisión para frío real. Es necesario registrar lecturas nuevas <12 °C y preferiblemente cerca de 12 °C y 21 °C en diferentes sesiones. Los valores sintéticos NO son mediciones reales.

## Orden de pasos
1. Abrir `01_COLAB/Reentrenar_TinyML_Calibrado.ipynb` en Colab.
2. Subir el CSV único y ejecutar todas las celdas. El modelo previo **NO ES VÁLIDO** con los nuevos umbrales.
3. Descargar `modelo_calibrado_exportado.zip`, extraer su `model.h` en `03_ESP32_CAM/TinyML_Calibrado/`.
4. Abrir `TinyML_Calibrado.ino`, seleccionar AI Thinker ESP32-CAM y cargar con Arduino IDE, monitor 115200.
5. Inicialmente `MODO_CALIBRACION=true`: los LEDs siguen la referencia 12/21; `CLASE_RED` indica la clasificación neuronal, que debe probarse aparte.
6. Validar con nuevas temperaturas reales (especialmente <12 y cerca de 12/21). Solo cuando coincidan, cambiar `MODO_CALIBRACION=false` y recompilar.
7. Cerrar Monitor Serie, ejecutar `04_PANEL_HTML/iniciar.cmd`, abrir http://127.0.0.1:8765 y conectar al COM.

**Hardware sin cambios:** DHT22 GPIO13; LEDs azul GPIO14, verde GPIO15, rojo GPIO2, cada LED con 220 Ω; tierras comunes.

**Importante:** `model.h` NO está incluido porque debe exportarse tras entrenar nuevamente. No compilar `TinyML_Calibrado.ino` antes de colocarlo. La validación por separación aleatoria de muestras sintéticas puede sobreestimar la capacidad real.
