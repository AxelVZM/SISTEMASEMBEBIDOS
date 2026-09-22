# Andes Maqanakuy 2.0 — despliegue en tu EC2

("Maqanakuy" = pelea/combate en quechua). Juego de pelea 1v1 en tiempo real (Node.js + Socket.io). Incluye rondas al mejor de tres, cronómetro, combos, alcance y altura de golpes, bloqueo, retroceso, estadísticas diferentes por luchador y controles de teclado o táctiles.

## Qué contiene esta carpeta
- `server.js` → servidor (salas, rondas, cronómetro, hitboxes, combos y validación de movimiento)
- `public/index.html`, `public/style.css`, `public/game.js` → lo que se ve en el navegador
- `public/img/` → 42 sprites limpios (6 personajes × 7 poses), sin restos magenta o verde
- `package.json` → dependencias (`express`, `socket.io`)

## Controles
| Tecla | Acción |
|---|---|
| **A** / **D** | Moverse a la izquierda / derecha |
| **W** | Saltar |
| **S** | Agacharse |
| **U** | Bloquear (mantener presionado — reduce el daño recibido ~75%) |
| **J** | Golpe alto (se esquiva agachándose) |
| **K** | Patada baja (se esquiva saltando) |
| **L** | Especial |

En computadora, los ataques se controlan solamente con teclado y las recargas aparecen como indicadores, no como botones. En celulares aparecen controles táctiles. Cada técnica tiene alcance, altura y retroceso propios.

## Sistema de combate
- Partidas al mejor de tres rondas, con 60 segundos por ronda.
- Combos: encadena impactos dentro de 1.2 segundos para aumentar el daño.
- Movimiento validado por el servidor para limitar teletransportes y trampas.
- Cada personaje tiene vida, velocidad, potencia, defensa, alcance y especial propios.
- Al terminar se muestran impactos, combo máximo, daño causado y bloqueos.

## Música ambiental
La música se carga de forma invisible e intenta comenzar al entrar al sitio. Algunos navegadores impiden el sonido antes de la primera interacción; en ese caso se activa automáticamente con el primer clic o tecla, sin mostrar controles ni avisos.

## 0. Pruébalo primero en tu computadora (antes de tocar AWS)
Así lo revisas tú misma sin depender del servidor ni del Security Group:

```bash
cd andes-maqanakuy
npm install
node server.js
```
Verás: `Servidor de Andes Maqanakuy corriendo en el puerto 3000`

Abre **dos pestañas** (o una normal + una de incógnito) en:
```
http://localhost:3000
```
- En la pestaña 1: pon un nombre → "Crear sala" → copia el código de 4 letras
- En la pestaña 2: pon otro nombre → pega el código → "Unirse a sala"
- Confirma que la música empiece al entrar o, si el navegador bloquea el autoplay, después del primer clic
- Ambas eligen personaje (cuando las dos eligen, empieza la pelea automáticamente y la pantalla pasa a modo pantalla completa)
- Haz clic **dentro de la arena** de cada pestaña (para que el navegador entregue el foco de teclado a esa ventana) y prueba:
  - **A/D** en cada pestaña — el personaje correspondiente debe moverse y el rival debe verlo moverse en la otra pestaña
  - **W** (salto) y **S** (agachar) — deben verse ambos gestos
  - **U** mantenido — debe sonar el bloqueo y reducir el daño que recibe ese jugador
  - **J / K / L** — deben sonar los golpes, cambiar la pose (puñete/patada) y el rival debe pasar a la pose de "golpeado"
  - al llegar a 0 de vida aparece la pose de KO real (tirado en el suelo) y la pantalla de "Ganaste/Perdiste"
  - el botón "Revancha" reinicia vida y posición de ambos

Para detener el servidor local: `Ctrl + C` en la terminal.

Cuando ya te guste cómo se ve/juega, sigue con los pasos de abajo para subirlo al EC2.

## 1. Sube la carpeta a tu EC2
Desde tu computadora (reemplaza `tu-llave.pem` y la IP):
```bash
scp -i tu-llave.pem -r andes-maqanakuy ubuntu@TU_IP_PUBLICA:/home/ubuntu/
```
(usa `ec2-user@` en vez de `ubuntu@` si tu instancia es Amazon Linux)

## 2. Conéctate por SSH e instala Node.js (si no lo tienes)
```bash
ssh -i tu-llave.pem ubuntu@TU_IP_PUBLICA

# Instalar Node.js 20 (Ubuntu):
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## 3. Instala dependencias y corre el servidor
```bash
cd /home/ubuntu/andes-maqanakuy
npm install
node server.js
```
Deberías ver: `Servidor de Andes Maqanakuy corriendo en el puerto 3000`

## 4. Abre el puerto en el Security Group de tu EC2
En la consola de AWS → EC2 → tu instancia → pestaña "Security" → Security Group → Edit inbound rules → Add rule:
- Type: Custom TCP
- Port: 3000
- Source: 0.0.0.0/0 (o restringido si prefieres)

## 5. Entra desde el navegador
```
http://TU_IP_PUBLICA:3000
```
Un jugador crea sala (le da un código de 4 letras), el otro se une con ese código desde otra pestaña, celular o computadora.

## 6. (Recomendado) Que el servidor no se caiga al cerrar la terminal SSH
```bash
sudo npm install -g pm2
pm2 start server.js --name andes-maqanakuy
pm2 save
pm2 startup   # sigue las instrucciones que te muestre
```

## Qué necesito de ti para mejorarlo (opcional)
No necesito nada más para que funcione. Si quieres subir el nivel:
- Si quieres audio real (grabado) en vez de sintetizado, archivos .mp3/.wav cortos de golpe/patada/especial.
- Si quieres HTTPS (candado verde) en vez de solo http://IP:3000, dime si tienes un dominio apuntando a la IP del servidor.
- Si tienes hojas de sprites con más cuadros por pose, puedo usarlas para animaciones más fluidas.
- Si quieres otra canción de fondo, pásame el link de YouTube y la cambio.

## Modos de juego (v2.1)
- Historia: combate consecutivo contra los 6 personajes controlados por IA.
- Local: combate contra un rival controlado por IA.
- Multijugador: crear o unirse a una sala online.
- Música: control desde la pantalla principal y pausa automática al entrar en batalla.
- Configuración: activar/desactivar música de menú y efectos de sonido.
