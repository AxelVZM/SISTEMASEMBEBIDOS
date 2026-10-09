# Despliegue de Rastro en AWS

## Despliegue actual (EC2 + PM2 + Nginx)

| Elemento | Valor |
| --- | --- |
| Panel | `http://18.191.113.248/movimiento/` |
| API | `http://18.191.113.248/movimiento/api` |
| WebSocket | `ws://18.191.113.248/movimiento/ws` |
| Proceso PM2 | `movimiento-api` (puerto interno 8080) |

La app ya trae por defecto la URL de AWS y la clave CARTO, así que basta con:

```powershell
flutter build apk --release
```

(Se pueden sobrescribir con `--dart-define=API_URL=...` y `--dart-define=CARTO_API_KEY=...`).

Actualizar el servidor (instala dependencias, verifica la base de datos,
migra datos antiguos, configura Nginx y reinicia solo `movimiento-api`):

```bash
cd ~/SISTEMASEMBEBIDOS && git pull && python3 TAREA3/backend/actualizar_servidor.py
```

La configuración de Nginx necesaria (WebSocket con `Upgrade`, sin buffering y
timeouts largos) está en `backend/nginx-movimiento.conf`.

### Base de datos: PostgreSQL

```
Celular ──POST/GET (HTTP keep-alive)──► API (EC2) ──SQL (SSL)──► PostgreSQL (RDS)
                                         │
Panel  ◄──GET (historial) + WebSocket ───┘  (cada punto se difunde al instante)
```

Tablas (se crean solas al arrancar): `users`, `devices` y `locations`
(índice `device_id + ts`, `sample_id` único para no duplicar puntos).

El servidor difunde cada punto al panel **antes** de escribirlo; la escritura
en PostgreSQL es un `INSERT` de varias filas (inmediato si la base está libre,
agrupado si llegan muchos puntos a la vez). El POST del celular responde
cuando el punto ya está guardado. Prueba local: confirmación ~20 ms, envío →
panel ~2 ms, ~2700 puntos/s con 50 celulares simultáneos.

**Opción A (en uso): PostgreSQL en la misma EC2, gratis.** Un solo comando
instala PostgreSQL en modo liviano (~60-80 MB de RAM, solo `localhost`), crea
swap de 1 GB si hace falta, genera usuario y contraseña, escribe `.env`,
programa un respaldo diario (`/var/backups/movimiento`, 7 días), migra los
datos antiguos y reinicia solo `movimiento-api`:

```bash
cd ~/SISTEMASEMBEBIDOS && git pull
python3 TAREA3/backend/instalar_postgres_local.py --simular   # opcional: ver qué hará
python3 TAREA3/backend/instalar_postgres_local.py
```

Restaurar un respaldo: `sudo -u postgres pg_restore -d movimiento --clean /var/backups/movimiento/movimiento-AAAAMMDD.dump`.

**Opción B: AWS RDS.** Crear la base en RDS (una sola vez):

1. Consola AWS → **RDS** → **Crear base de datos** (misma región que la EC2: Ohio `us-east-2`).
2. **Creación estándar** · Motor **PostgreSQL** · Plantilla **Capa gratuita**.
3. Identificador `movimiento-db`, usuario `postgres`, contraseña segura (guárdala).
4. Clase `db.t4g.micro` (o `db.t3.micro`), almacenamiento 20 GB.
5. **Conectividad** → *Conectarse a un recurso informático EC2* → elige tu EC2
   (AWS crea los grupos de seguridad para el puerto 5432). Acceso público: **No**.
6. **Configuración adicional** → *Nombre de base de datos inicial*: `movimiento`.
7. Crear y esperar ~5-10 min a que el estado sea **Disponible**. Copiar el **Punto de enlace**.

**Configurar el servidor:** en la EC2, copiar `backend/.env.example` a
`backend/.env` y completar `PGHOST` (punto de enlace), `PGUSER`,
`PGPASSWORD` y `PGDATABASE`. Luego ejecutar el script de actualización.

### API REST

| Método | Ruta | Uso |
| --- | --- | --- |
| POST | `/api/devices` | Registrar/actualizar celular |
| POST | `/api/devices/:id/locations` | Un punto GPS (responde al guardarse) |
| POST | `/api/devices/:id/locations/batch` | Lote de puntos pendientes (offline) |
| POST | `/api/devices/:id/heartbeat` | Sigo activo / `active:false` al detener |
| GET | `/api/time` | Hora del servidor (RTT y desfase de reloj) |
| GET | `/api/devices` | Lista de dispositivos y estado online |
| GET | `/api/devices/:id/location` | Última posición |
| GET | `/api/devices/:id/history?lastSession=true` | Último recorrido |
| GET | `/api/devices/:id/history?from=ISO&to=ISO` | Puntos en un rango |
| DELETE | `/api/devices/:id/locations` | Borrar ruta |
| DELETE | `/api/devices/:id` | Eliminar dispositivo y su ruta |
| GET | `/api/health`, `/api/metrics` | Estado, latencias y ping a la BD |

## Errores frecuentes

- **No aparece el celular:** revisa que la app tenga permiso de ubicación y que `http://18.191.113.248/movimiento/api/health` responda.
- **`/api/health` dice `desconectada`:** PostgreSQL no responde. En la EC2: `sudo systemctl status postgresql` y `pm2 logs movimiento-api --lines 30`.
- **Mapa en blanco:** CARTO solo tiene mosaicos hasta zoom 18 (ya configurado); revisa la conexión a internet.
- **Saltos con el celular quieto:** bajo techo el GPS tiene ±10-20 m de error; prueba al aire libre.
- **Respaldos:** `/var/backups/movimiento` (uno por día, 7 días).
