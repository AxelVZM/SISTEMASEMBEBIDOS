# ANDES MAQANAKUY - GAMEPLAY V6.1

## Correcciones

- Corregida la deformación horizontal de todos los personajes.
- El motor usaba `aspect-ratio: 181/99` aunque cada frame real mide 160x240.
- Ahora los sprites usan relación `2/3`, ancho automático y sin estiramiento por flexbox.
- Se mantienen las escalas propias de Coya, Cuy, Gallito, Jaguar, Oso y Gato.

## Dificultad IA

Se bajó ligeramente la dificultad de los tres niveles, sin convertirlos en IA pasiva:

- Fácil: reacción un poco más lenta y menor defensa/dash.
- Medio: menos presión, bloqueos, esquivas y ataques fuertes.
- Avanzado: sigue siendo competitivo, pero con reacción menos perfecta y menor frecuencia de defensa/especiales.

## Versión

`gameplay-v6.1`
