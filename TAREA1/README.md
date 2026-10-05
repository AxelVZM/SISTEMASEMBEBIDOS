# PUÑO DE HIERRO

Videojuego de lucha 2D desarrollado con **HTML, CSS y JavaScript puro**, ejecutado directamente en el navegador.

El juego utiliza **HTML5 Canvas** para el renderizado, animaciones, colisiones, HUD, partículas y efectos visuales. También incorpora inteligencia artificial, controles de teclado y táctiles, sistema de combos, bloqueo, ataques especiales y sonido generado mediante **Web Audio API**.

## Características

- Combate rápido contra un rival aleatorio.
- Modo historia.
- 7 personajes jugables.
- 3 escenarios.
- 3 niveles de dificultad.
- Sistema de vida y energía.
- Golpes débiles, fuertes y patadas.
- Ataques bajos y aéreos.
- Ataques especiales.
- Sistema de bloqueo.
- Combos y contragolpes.
- Inteligencia artificial para el rival.
- Efectos de partículas y textos de daño.
- Controles para teclado y dispositivos táctiles.
- Sonidos generados directamente desde el navegador.

## Personajes

- Kaito Wolfe
- Rhea Storm
- Boris Kraven
- Nyx Shade
- Ozor el Furioso
- Jumpa Veloz
- Zeta-9

## Escenarios

- Dojo Ancestral
- Calle Nocturna
- Arena Futurista

## Controles

| Acción | Tecla |
|---|---|
| Mover izquierda / derecha | A / D |
| Saltar | W |
| Agacharse | S |
| Golpe débil | J |
| Golpe fuerte | K |
| Patada | L |
| Ataque especial | U |
| Bloquear | I |
| Pausa | ESC |

### Movimientos adicionales

- `S + J`: golpe bajo.
- `S + L`: patada baja.
- `Salto + L`: patada aérea.

## Combos

El juego incluye combinaciones especiales, por ejemplo:

- `J + J + K`: Combo Furia.
- `J + L + U`: Combo Devastador.
- `L + L + K`: Combo Tormenta.

También existe un sistema de contragolpe que aumenta el daño cuando se golpea al rival durante el inicio de su ataque.

## Tecnología utilizada

- HTML5
- CSS3
- JavaScript
- HTML5 Canvas
- Web Audio API
- Nginx

El área principal del juego utiliza un canvas de **960 × 540 píxeles** y un bucle de renderizado mediante `requestAnimationFrame`.

## Estructura

El juego está contenido principalmente en un solo archivo:

```text
TAREA1/
└── tekken.html
```

El archivo contiene la interfaz HTML, los estilos CSS y la lógica JavaScript del juego.

## Ejecución local

Puede ejecutarse abriendo `tekken.html` en un navegador moderno.

También puede servirse mediante un servidor web. Por ejemplo:

```bash
python3 -m http.server 8080
```

Después abrir:

```text
http://localhost:8080/tekken.html
```

## Despliegue con Nginx

En el servidor utilizado para el proyecto, el archivo se encuentra en:

```text
/var/www/html/tekken.html
```

La configuración de Nginx puede incluir:

```nginx
location = /tekken.html {
    root /var/www/html;
    try_files /tekken.html =404;
}
```

Esto permite servir el juego directamente desde Nginx sin interferir con otras aplicaciones ejecutadas mediante proxy inverso.

## Repositorio

```text
https://github.com/AxelVZM/SISTEMASEMBEBIDOS
```
