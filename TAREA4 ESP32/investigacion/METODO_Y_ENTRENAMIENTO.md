# Métodos aplicados y límites

## Base científica
- Bogahawatta y colaboradores, *Passive Identification of WiFi Devices At-Scale: A Data-Driven Approach*, IEEE LCN 2024. https://doi.org/10.1109/LCN60385.2024.10639764
- Bogahawatta y colaboradores, *Device Type Classification Using WiFi Probe Requests: From Signals to Insights*, IEEE TMC 2026. https://doi.org/10.1109/TMC.2026.3668688
- Waddar y colaboradores, *ESP32-Driven Real-Time Indoor Localization Using Wi-Fi RSSI and a Simple Path Loss Model*, IEEE ETCC 2025. https://doi.org/10.1109/ETCC65847.2025.11108539

Las publicaciones motivan el uso de atributos de probe requests y el suavizado RSSI con pérdida de propagación. Esta entrega es una adaptación experimental, no una reproducción de sus algoritmos, conjuntos de datos o resultados. La consulta disponible fue de resúmenes/metadatos; no se atribuye al código la exactitud reportada por los autores. El trabajo de localización emplea varios AP; este proyecto tiene un sensor y NO implementa trilateración. Se excluye el estudio BLE porque la versión trabaja solo con Wi-Fi.

## Implementación
1. El ESP32 escucha Wi-Fi 2,4 GHz en canales 1–11, alternándolos cada 300 ms. Se eliminan el controlador, cola, escaneo, clasificación y filas Bluetooth del firmware. En el protocolo de estado y la base permanecen campos históricos BLE en cero por compatibilidad; no representan detecciones nuevas.
2. RSSI suavizado: EMA = 0,75 * anterior + 0,25 * muestra. El panel usa d=10^((A-RSSI)/(10n)). No estima posición, vivienda o negocio. No se ofrece intervalo de confianza sin datos medidos. Valores fuera de escala se indican, no se recortan silenciosamente en el CSV.
3. Huella v1, solo probe requests: orden de IDs; contenido de Supported Rates (1), Extended Supported Rates (50), HT Capabilities (45), Extended Capabilities (127), VHT Capabilities (191); de cada IE vendor (221), solo sus primeros 4 bytes (OUI/tipo). Otros IDs se conservan con longitud 0. No se guarda SSID, MAC, nombres ni UUID en la firma. Máximo 96 bytes; desbordamiento o ausencia de capacidades impide la clasificación por huella. El parser rechaza TLV truncados. HE y temporización entre paquetes quedan fuera de esta versión; el salto de canales impide tratarlos como intervalos completos de emisión.
4. WPS/P2P explícito y pistas por nombres continúan en la placa. El fabricante IEEE solo no asigna tipo/modelo. En el panel, únicamente una fila sin tipo determinado puede recibir un tipo probable por coincidencia exacta con el catálogo. Los conflictos no se sobreescriben. El modelo probable se muestra en Detalles y no sustituye el modelo WPS declarado. No se unen MAC aleatorias ni se atribuye una identidad física.
5. Las huellas viajan por USB → navegador/puente → API EC2 → SQLite → consulta remota. La clasificación por catálogo y la distancia se calculan en el panel. La ruta opcional antigua de subida directa a Lambda conserva su función previa, pero no incluye las huellas nuevas ni este clasificador.

## Crear el catálogo
El archivo web/wifi_catalog.json se entrega vacío. No hay capturas reales etiquetadas en esta entrega. Una lista comercial de celulares/laptops no proporciona firmas de radio.

1. En un entorno controlado observa equipos propios identificados por modelo y unidad física. Usa varias unidades de cada modelo, versiones de sistema y sesiones separadas; observa actividad real de sondeo.
2. En Explorador pulsa Exportar huellas JSON. La demostración no exporta entrenamiento. Se exportan solo huellas completas. Cada fila incluye la MAC observada para facilitar su etiquetado manual en la sesión; no se usa como característica ni se supone identidad estable.
3. Rellena device_id (unidad física conocida), session_id (sesión experimental), type (phone/laptop/unknown), brand, model y source (procedencia y condiciones). Un rótulo WPS no es una etiqueta de referencia verificada. No atribuyas filas de vecinos a tu dispositivo.
4. Combina las capturas de entrenamiento en train.json y las de validación en test.json. Usa unidades físicas Y sesiones disjuntas. Incluye desconocidos y modelos con capacidades parecidas. Mínimo para publicar una firma: dos unidades en entrenamiento y al menos una unidad diferente en validación. Es un mínimo operativo, no una garantía estadística.
5. Desde la carpeta del proyecto ejecuta:

```bash
python3 herramientas/entrenar_huellas.py train.json test.json --output web/wifi_catalog.json
```

La herramienta agrupa firmas exactas, rechaza etiquetas contradictorias y firmas con una sola unidad, y publica solo candidatos sin errores en sus muestras de validación. Rechaza solapamiento de device_id o session_id entre conjuntos. Una firma compartida puede seguir coincidiendo con un modelo desconocido no evaluado: por eso se informa «probable».

6. Revisa el informe (precisión entre aceptadas y cobertura antes de seleccionar entradas). Como test se usa para seleccionar entradas, NO es una evaluación final independiente. Realiza una tercera campaña con unidades/sesiones nuevas y modelos desconocidos; reporta cobertura, errores y confusión por clase/modelo. No balances resultados repitiendo miles de paquetes de un mismo aparato.
7. Sube el catálogo validado a web/wifi_catalog.json, reconstruye la aplicación en EC2 y recarga el panel. No necesitas recompilar la placa para cambiar el catálogo. El catálogo nunca contiene tokens.

## Qué aún requiere medición
Precisión real de tipo/modelo, RSSI de referencia por emisor, error de distancia en cada entorno, tasa de pérdida con muchos emisores, estabilidad térmica/eléctrica y comportamiento de cada antena. Las pruebas automáticas y compilación no sustituyen estas mediciones.
