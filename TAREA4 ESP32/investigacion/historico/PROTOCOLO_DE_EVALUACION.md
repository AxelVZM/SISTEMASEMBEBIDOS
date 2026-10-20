> V7.1: antes de ensayos de conteo, desactiva la subida automática a AWS y espera la estabilización. Las pausas de radio por conexión o HTTPS se marcan como incidencias en el ensayo. Probar tu red durante un ensayo también afecta a la cobertura. La campaña de latencia/colas/pérdidas sigue pospuesta.

# Evaluación del conteo — sin campaña de latencia todavía

El número que entrega el firmware es de **direcciones observadas**, no de equipos únicos. Los ensayos comparan ese número con una cantidad conocida de equipos físicos para cuantificar la diferencia bajo condiciones documentadas. No validan una identificación de marca/modelo ni separan por sí mismos falsos positivos y falsos negativos individuales.

## Ensayo inicial recomendado

1. Prepara un entorno controlado con equipos propios y documenta otras redes/emisores presentes. No alteres el tráfico de terceros para «aislar» el ensayo.
2. Anota número de equipos, radios habilitadas, estado de pantalla/ahorro, modelo conocido para el informe, posibles MAC privadas, ubicación y orientación del ESP32. Es documentación experimental; no se registra un inventario en el detector.
3. Conecta USB y entra en **Ensayos**. Selecciona Wi-Fi o BLE, cantidad física conocida y duración de 2/5/10 minutos. Puedes poner cero para una condición de referencia sin equipos de prueba.
4. El asistente espera 60 s de estabilización, después toma una muestra de conteo por cada intervalo nominal de 5 s cuando llega telemetría válida. No inicia ni detiene la captura.
5. Mantén equipos y entorno estables. Los equipos deben emitir tramas/anuncios compatibles; encender una radio no garantiza que emita durante cada ventana.
6. Al terminar, exporta el CSV. Repite al menos tres veces por condición y prueba cantidades distintas. Los resultados son del entorno observado, no del interior físico de una habitación identificado automáticamente.
7. Haz ensayos de Wi-Fi y BLE por separado. No sumes resultados entre protocolos como aparatos únicos.

## Métricas calculadas

Con cantidad conocida N y muestras de direcciones Cᵢ:

- Media observada = suma(Cᵢ)/m.
- MAE del conteo = suma(|Cᵢ−N|)/m.
- Sesgo = media(Cᵢ)−N.
- Error absoluto relativo medio = 100·MAE/N, solo si N>0.
- Mínimo, máximo y cantidad de muestras recibidas.

Una media igual a N no demuestra que se detectaron los mismos N aparatos: una omisión y una duplicación pueden compensarse. Es incorrecto llamar a 100 %−error una precisión de identificación. La suma de diferencias tampoco permite atribuir cuáles dispositivos faltaron.

El asistente marca incidencias si la radio relevante está indisponible, se alcanza capacidad, existen omisiones acumuladas del protocolo en la sesión o se interrumpe telemetría. Es conservador: omisiones previas en el mismo arranque también marcan el ensayo. Un reinicio/desconexión cancela el ensayo; la captura del ESP32 continúa mientras tenga energía. Un ensayo cancelado no se presenta como completado.

Los ensayos se almacenan solo en ese navegador, hasta 100 sesiones; no se escriben como etiquetas en el firmware. El historial de conteos del panel conserva hasta 4 horas, con límite de puntos. Borrar datos del navegador elimina esos historiales, no los segmentos flash del ESP32. La demostración está bloqueada para ensayos y no contamina el historial de mediciones.

## Comprobaciones físicas pendientes

- Recepción de Wi-Fi y BLE conocidos, ciclos de alternancia y detección sin una red asociada.
- Inicialización y heap bajo ocupación alta, sin corrupción ni reinicios prolongados.
- Saturación con tablas de 96 Wi-Fi y 32 BLE; comprobar aviso de cobertura parcial.
- Funcionamiento sin accesorios y después con OLED/RTC/LED.
- Autonomía, retención flash y fecha tras cortes de energía.
- Comparación en entorno controlado y condiciones reales documentadas.

La campaña instrumental de **latencia, longitud de cola y pérdidas** se mantiene para la fase posterior. Los contadores de omisiones son indicadores de diagnóstico; no constituyen una campaña de medición ni un plazo máximo de respuesta demostrado.
