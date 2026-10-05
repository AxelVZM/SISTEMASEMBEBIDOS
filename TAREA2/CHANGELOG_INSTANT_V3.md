# Andes Maqanakuy — Instant Combat V3

## Prioridad: respuesta inmediata

- Ataques sin cooldown: golpe, golpe fuerte, patada, patada fuerte y especial no tienen tiempo de recarga.
- La animación local arranca en el mismo `keydown`, antes de esperar respuesta del servidor.
- Startup jugable de ataques reducido a 0 ms: la validación de impacto ocurre inmediatamente.
- Recovery jugable reducido a 0 ms: puedes encadenar ataques sin esperar a que termine la animación anterior.
- Se permite cancelar un ataque con otro ataque para cadenas rápidas.
- Mantener J/K permite repetir ataques usando el autorepeat del teclado.
- Movimiento permitido durante el estado de ataque para evitar sensación de bloqueo.
- Sincronización de movimiento subida de ~20 Hz a ~50 Hz con paquetes `volatile` para descartar posiciones viejas en vez de acumular retraso.
- Velocidad de movimiento aumentada y transición a carrera más rápida.
- Dash responde más rápido y su espera se redujo a 220 ms.
- Pulsación larga táctil para ataques fuertes reducida de 300 ms a 180 ms.
- Indicadores de ataque permanecen siempre en estado listo; la barra de energía sigue siendo el requisito del especial.

## Se mantienen

- Daño únicamente dentro del rango/hitbox real.
- Esquiva por postura.
- Hitboxes, combos, energía, especiales por personaje, partículas, parallax y multijugador.
- KO, knockdown y estados de daño siguen bloqueando acciones para evitar estados imposibles.
