# Smooth Sprites V2

## Correcciones visuales
- Escala base independiente por personaje para conservar proporciones consistentes.
- Compensación de escala por estado/animación para evitar que golpes, patadas y especiales hagan que el personaje se encoja o crezca de forma abrupta.
- Se mantienen diferencias intencionales de tamaño: Oso es más grande; Gato/Cuy son más compactos.
- Spritesheets reducidos de 240x360 a 160x240 por frame conservando 22 estados x 4 frames.

## Rendimiento
- Menor tamaño de texturas de spritesheets y menor memoria gráfica necesaria.
- El render de sprites solo actualiza `background-position` cuando cambia realmente el frame.
- Barra de recargas limitada a ~20 actualizaciones por segundo en vez de 60.
- Niebla/parallax menos costoso para GPU.
- Movimiento local más ágil y carrera ligeramente más rápida.
- IA actualizada con menor intervalo de reacción.

## Combate
- Startup y recovery reducidos moderadamente para que los ataques respondan más rápido.
- Se mantienen hitboxes, energía, combos, dash, esquiva, especiales, partículas, pausa, mapas y multijugador.
- Se mantiene música distinta por escenario.

## Versión
`/healthz` devuelve `smooth-sprites-v2`.
