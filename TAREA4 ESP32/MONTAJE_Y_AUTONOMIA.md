> V7.1 conserva este montaje. La red es opcional: el estado OLED añade “RED - PAUSA RADIO” durante conexión/subida. Los envíos pueden aumentar el consumo; no se ha medido su efecto en batería.

# Montaje, accesorios y funcionamiento autónomo

## Materiales

| Material | Función | Necesidad |
|---|---|---|
| ESP32 clásico con BLE, flash 4 MB y cable de datos USB | Captura y programación | Ya disponible según tu proyecto |
| OLED SSD1306 I²C 128×64, lógica/alimentación compatibles con 3,3 V | Muestra conteos sin PC | Opcional; recomendado para exponer |
| LED externo + resistencia 330 Ω | Estado local del sensor | Opcional |
| RTC DS3231 compatible con 3,3 V y batería apropiada para el módulo | Conserva fecha/hora | Opcional |
| Protoboard y cables cortos | Montaje inicial | Según accesorios |
| Fuente USB estable de 5 V, con margen de corriente para placa y accesorios | Alimentación independiente | Para demostrar autonomía |
| Carcasa no metálica y soporte fijo | Protección y repetibilidad | Recomendados |

No se incorporan componentes físicos mediante software. Sin OLED/RTC el conteo y registro USB siguen disponibles; sin LED externo no habrá indicación luminosa visible aunque el pin se controle.

## Conexiones

Conecta/desconecta accesorios con la placa sin alimentación. Identifica las etiquetas reales de tu placa: el esquema es funcional y no representa la posición física de sus pines.

| Señal ESP32 | OLED SSD1306 | RTC DS3231 |
|---|---|---|
| GPIO21 | SDA | SDA |
| GPIO22 | SCL | SCL |
| 3V3 | VCC compatible con 3,3 V | VCC compatible con 3,3 V |
| GND | GND | GND |

Los dos accesorios comparten el bus I²C. Mantén cables cortos; las resistencias pull-up, si se requieren, deben ir a 3,3 V. Verifica las incorporadas en tus módulos y no conectes señales elevadas a 5 V al ESP32. El firmware usa 400 kHz, timeout de 10 ms y busca SSD1306 en **0x3C/0x3D**, DS3231 en **0x68**. No soporta SH1106; responder en I²C no autentica el modelo del accesorio.

LED: **GPIO25 → resistencia 330 Ω → ánodo del LED; cátodo → GND**. No lo conectes sin resistencia. Se utiliza un LED externo para no asumir el pin del LED integrado ni usar un pin de arranque como GPIO2. Los valores se pueden cambiar en `config.h`; LED_PIN=-1 lo deshabilita.

Alimenta la placa por su conector USB. No apliques 5 V al pin 3V3 ni a GPIO. Comprueba el esquema del módulo RTC: algunos incorporan un circuito de carga. Usa únicamente la batería y configuración compatibles con ese módulo; no supongas que cualquier pila de botón es intercambiable.

## Pantalla y LED

La OLED muestra «WIFI», «BLE» y sus conteos de direcciones recibidas en 60 s. La línea inferior alterna estado de radio/hora UTC y prioriza avisos. Actualiza aproximadamente cada segundo; un fallo de bus la deshabilita y vuelve a buscarla cada 30 s. Conectar accesorios debe hacerse apagado y reiniciando para el primer uso, aunque el firmware tenga recuperación.

LED, ciclo de 1,5 s:

- Un destello: estado normal de los módulos supervisados.
- Dos destellos: tabla Wi-Fi o BLE al límite de direcciones recientes.
- Tres destellos: revisar Wi-Fi, inicialización BLE o montaje del almacenamiento.

La ausencia de OLED/RTC no es un fallo crítico. El LED no certifica recepción de todos los emisores ni detecta si el LED físico está conectado. Las omisiones históricas aparecen como aviso en el panel.

## Hora, RTC y registro

Al conectar USB, el panel sincroniza automáticamente con la hora del PC si la placa no tiene hora válida o difiere más de 5 s. Esa operación no requiere Internet. Con RTC presente, escribe la fecha UTC y limpia OSF tras escribir correctamente; al arrancar lee el RTC solo si su calendario y estado son válidos. Se soportan fechas 2024–2099.

Sin RTC, el reloj de software dura hasta cortar energía. Sin fecha válida, el CSV deja `fecha_utc` vacía y conserva sesión/uptime_ms. No inventa una fecha. La batería mantiene el RTC, no alimenta el ESP32. La capacidad de conservar hora depende del montaje y batería reales.

El HTML muestra hora según la configuración local del navegador; OLED y CSV usan UTC. Para Lima, UTC−5, el navegador normalmente hace la conversión si el PC está configurado correctamente.

## Prueba de autonomía que debes realizar

1. Carga V7, conecta el panel, verifica conteos y descarga una copia del registro inicial.
2. Apaga, conecta la placa a una fuente USB independiente del PC y verifica patrón LED/OLED si los instalaste.
3. Déjala operar al menos 10 minutos en un entorno documentado. No necesita navegador ni red.
4. Vuelve al PC y descarga el registro: comprueba nuevas sesiones/resúmenes y conteos separados. Los tiempos de arranque deben aparecer aunque no hubiera RTC.
5. Si instalaste RTC, verifica conservación de fecha tras un corte y ausencia de avisos de hora.
6. Repite con la carcasa final y observa si empeora la recepción o se reinicia por alimentación.

Esta prueba requiere tu placa; no está realizada desde aquí.

## Carcasa y repetibilidad

Usa una caja no metálica, protege soldaduras y evita que se cortocircuiten. Deja libre la zona de antena, no la cubras con metal ni apoyes batería/cables contra ella. No tapes componentes que se calienten. Fija la orientación y altura del sensor; anota ubicación, proximidad a paredes, objetos metálicos y alimentación en cada ensayo.

No se incluye un archivo de carcasa para imprimir porque no conocemos las dimensiones exactas de tu placa ni módulos. La guía permite un montaje funcional; un diseño mecánico a medida necesita esas dimensiones.
