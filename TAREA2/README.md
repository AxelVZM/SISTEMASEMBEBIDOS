# ANDES MAQANAKUY — MENÚ Y MAPAS V8

Esta versión mantiene el balance V7 y añade selector de mapas desde el menú principal y una guía visual de controles.

- El mapa elegido se usa directamente en Modo Local.
- En Historia es el escenario inicial y los siguientes rotan desde ese punto.
- Al crear una sala online, el anfitrión comienza con ese mapa seleccionado y aún puede cambiarlo dentro de la sala.
- Se incluyen controles de movimiento, salto, agacharse, bloqueo, golpe, patada, especial, ataque fuerte y dash.

# ANDES MAQANAKUY — Netplay V5

Juego de pelea 2D inspirado en Cusco y los Andes. Incluye Historia sin diálogos/mapa narrativo, Local contra IA y Multijugador por salas con Socket.IO.

## Novedades de Netplay V5

- Sprites renovados para Coya, Cuy, Gallito, Jaguar, Oso y Gato Andino manteniendo sus colores, vestimenta y rasgos principales.
- Movimiento local con predicción inmediata: el personaje responde antes de esperar confirmación del servidor.
- Movimiento remoto interpolado y con extrapolación leve según el ping para que el rival no avance a saltos.
- Canal de red ligero para movimiento; el servidor ya no transmite el estado completo de la partida en cada pequeño paso.
- Snapshots autoritativos de corrección cada 300 ms para evitar desincronización sin saturar la conexión.
- Dash, salto, bloqueo y ataques con animación local inmediata.
- Ataques sin cooldown visible. Existe solo una protección técnica mínima anti-flood en servidor.
- Repetición fluida al mantener golpe/patada y controles táctiles con respuesta inmediata.
- IA local actualizada con movimiento a 75 ms, bloqueo, esquiva, dash y decisiones separadas del movimiento.
- Modo automático de rendimiento: si el navegador cae de FPS se reducen filtros/parallax costosos y se reactivan al recuperarse.
- Reconexión rápida, ping visible, espectador y revancha sincronizada.

## Sistema de combate

- Máquina de estados.
- Hitboxes/hurtboxes.
- Golpes ligeros/fuertes, barrido y ataque aéreo.
- Combos.
- Energía 0–100 y especial desde 50.
- Especial único por personaje.
- Dash/esquiva.
- Bloqueo alto/bajo.
- Partículas, cámara y efectos configurables.
- Música de menú y música por escenario.
- Escenarios del Cusco con parallax.

## Controles

- A / D: movimiento.
- W: salto.
- S: agacharse.
- U: bloquear; S + U: bloqueo bajo.
- J: golpe.
- K: patada.
- L: especial.
- Shift + J: golpe fuerte.
- Shift + K: patada fuerte.
- Doble A / D: dash.
- ESC: pausa.

Las letras de control no aparecen impresas en la interfaz de batalla.

## Ejecutar localmente

```bash
npm install
npm start
```

Abrir:

```text
http://localhost:3000
```

## Verificar versión

```bash
curl http://127.0.0.1:3000/healthz
```

Debe devolver:

```json
{"ok":true,"app":"andes-maqanakuy","version":"netplay-v5"}
```

## AWS

Consulta `DEPLOY_AWS.md`. Se mantienen `ecosystem.config.cjs` para PM2 y la configuración de Nginx + WebSocket.

Para actualizar tu EC2 después de subir esta versión a GitHub:

```bash
cd ~/SISTEMASEMBEBIDOS/TAREA2
git pull origin main
npm install
pm2 restart andes-maqanakuy
pm2 save
```

Consulta `CHANGELOG_NETPLAY_V5.md` para el detalle técnico.

## Gameplay V6

Esta versión corrige la visualización de personajes y añade dificultad para los modos con IA.

### Probar localmente

```powershell
npm install
$env:PORT=3100
npm start
```

Abrir: `http://127.0.0.1:3100/?v=balance-v7`

Verificación: `http://127.0.0.1:3100/healthz` debe mostrar `balance-v7`.

### Dificultad

- Fácil: reacción más lenta, menos bloqueo/esquiva y ataques principalmente básicos.
- Medio: equilibrio general.
- Avanzado: reacción rápida, mejor control de distancia, bloqueos, esquivas, dash, fuertes y especiales más frecuentes.


## V6.1 - Ajuste IA y proporción de personajes
- IA Fácil, Medio y Avanzado ligeramente menos agresiva.
- Menos bloqueos/esquivas/dash y una reacción un poco más humana.
- Corregida la relación de aspecto de los frames: 160x240 (2:3).
- Los personajes ya no se ensanchan horizontalmente.


## Balance V7

- Vida aumentada y daño reducido para que las peleas duren más.
- Rondas de 90 segundos.
- Anti-spam corto entre ataques, sin volver lentos los controles.
- Especiales cuestan 70 de energía.
- Barra de guardia con ruptura y regeneración.
- Stun breve al cuarto impacto de un combo largo.
- Knockback mayor para separar luchadores.
- IA con más pausas entre ataques en Fácil, Medio y Avanzado.
