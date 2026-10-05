# Andes Maqanakuy — NETPLAY V5

## Jugabilidad local/online
- Movimiento del jugador local con predicción inmediata.
- Canal ligero `movimiento_jugador` para no enviar el estado completo en cada paso.
- Interpolación y pequeña extrapolación del rival según latencia medida.
- Snapshots autoritativos de corrección a baja frecuencia para evitar drift.
- Secuencia de inputs de movimiento para descartar paquetes viejos.
- Dash con predicción local y reconciliación suave.
- Animación local inmediata para salto, bloqueo, dash y ataque.
- Ataques siguen sin cooldown visible; protección mínima anti-flood de 48 ms en servidor.
- Repetición mantenida de golpe/patada sin depender del autorepeat del sistema operativo.

## IA local
- IA actualizada a 75 ms para movimiento mucho más continuo.
- Decisiones separadas del movimiento para que no ataque de forma absurda cada tick.
- Reacciona a amenazas con bloqueo o esquiva.
- Se acerca, retrocede y usa dash con más naturalidad.

## Render / rendimiento
- Sprites nuevos integrados para los seis personajes.
- Escala fija por personaje/estado para eliminar encogimientos y crecimientos artificiales.
- Cliente reduce automáticamente efectos costosos si detecta FPS bajos y los reactiva si se recupera.
- Menos trabajo visual en sombra, niebla y sacudidas cuando entra el modo automático de rendimiento.
- YouTube se solicita en calidad baja para reducir carga durante la música del escenario.

## Red
- Socket.IO con reconexión rápida y `rememberUpgrade`.
- Movimiento se transmite como evento volátil; golpes y cambios de vida siguen siendo fiables/autoritativos.
- `serverTime` incluido en snapshots.
- `/healthz` devuelve `netplay-v5`.
