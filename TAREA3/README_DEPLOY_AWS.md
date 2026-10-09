# Despliegue de Rastro en AWS

## Arquitectura

- **Flutter Android/iOS:** captura GPS solo después de login, consentimiento y permiso del sistema.
- **API:** Node.js + Express, JWT, validación, rate limiting y WebSocket en `/ws`.
- **Dashboard:** HTML/CSS/JavaScript servido por la API, Leaflet + Carto/OpenStreetMap.
- **Desarrollo local:** persistencia JSON en `backend/data/movimiento.json` para evitar dependencias nativas.
- **Producción recomendada:** ECS/Fargate para la API, DynamoDB para `users`, `devices` y `locations`, API Gateway/WebSocket o el WebSocket del servicio, CloudWatch para logs.

## Requisitos

- Flutter SDK y Android SDK.
- Node.js 22 o superior.
- Docker Desktop para construir la imagen.
- AWS CLI configurado con un perfil autorizado.
- Un dominio administrado en Route 53 y un certificado ACM.

## Variables de entorno

Copiar `backend/.env.example` como `backend/.env` y cambiar los valores:

```powershell
Copy-Item backend/.env.example backend/.env
```

Nunca subir `.env`, contraseñas, claves JWT ni credenciales AWS al repositorio.

Variables principales:

- `PORT`: puerto HTTP, por defecto `8080`.
- `JWT_SECRET`: clave larga y aleatoria.
- `CORS_ORIGIN`: origen exacto del dashboard.
- `DB_FILE`: archivo local de desarrollo.
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`: usuario inicial local.
- `JWT_EXPIRES_IN`: duración del token.

## Ejecutar localmente

Terminal 1, API y dashboard:

```powershell
Set-Location backend
npm install
npm start
```

Abrir `http://localhost:8080` y entrar con las credenciales definidas en `.env`.

Validar salud:

```powershell
Invoke-RestMethod http://localhost:8080/api/health
```

Para un celular físico, la API debe escuchar en la IP LAN del computador. Ejecutar Flutter con:

```powershell
flutter pub get
flutter run -d ID_DEL_CELULAR --dart-define=API_URL=http://IP_DEL_PC:8080/api
```

En el emulador Android se usa por defecto `http://10.0.2.2:8080/api`.

## Docker

Construir y ejecutar:

```powershell
docker build -t movimiento-api ./backend
docker run --name movimiento-api -p 8080:8080 --env-file backend/.env -v movimiento-data:/app/data movimiento-api
```

En producción, no usar el archivo JSON como almacenamiento principal. Migrar a DynamoDB o PostgreSQL administrado.

## Modelo de datos de producción

### users

- `userId` (partition key)
- `email`
- `passwordHash` o identidad de Cognito
- `createdAt`

### devices

- `deviceId` (partition key)
- `userId` (GSI para listar por usuario)
- `name`, `platform`, `appVersion`, `model`
- `lastSeen`, `battery`, `consentedAt`

### locations

- `deviceId` (partition key)
- `timestamp` (sort key)
- `latitude`, `longitude`, `accuracy`, `speed`, `heading`, `battery`

El índice compuesto `deviceId + timestamp` permite recuperar el último punto y el historial por rango temporal. Aplicar TTL si la política de retención lo permite.

## Endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/devices`
- `POST /api/devices/:deviceId/locations`
- `GET /api/devices`
- `GET /api/devices/:deviceId/location`
- `GET /api/devices/:deviceId/history?from=ISO&to=ISO`
- `GET /api/health`
- `WS /ws?token=JWT`
- `GET /api/metrics` devuelve promedio, P50, P95, P99, máximo, porcentaje bajo
  de 1000 ms y muestras descartadas desde el arranque del proceso. No es una
  certificación de rendimiento: la prueba de campo debe ejecutarse durante al
  menos 10 minutos y conservar sus datos.

Todos los endpoints de dispositivos requieren `Authorization: Bearer JWT` y verifican que el dispositivo pertenezca al usuario autenticado.

## AWS paso a paso

1. Crear un repositorio ECR y subir la imagen Docker.
2. Crear un cluster ECS y un servicio Fargate en subredes privadas.
3. Crear un Application Load Balancer HTTPS hacia el puerto `8080`.
4. Guardar `JWT_SECRET` y credenciales en Secrets Manager o SSM Parameter Store.
5. Configurar `CORS_ORIGIN` con el dominio real del panel.
6. Crear tablas DynamoDB con las claves indicadas y reemplazar el repositorio JSON.
7. Enviar logs de stdout/stderr a CloudWatch.
8. Usar API Gateway WebSocket si se requiere escalado independiente del canal en tiempo real; configurar el mismo JWT en `$connect`.
9. Crear certificado ACM en la región del dominio.
10. Crear registro Route 53, por ejemplo `tracking.midominio.com`, apuntando al CloudFront/ALB.
11. Publicar el dashboard estático en S3 + CloudFront si se separa del backend. Mantener `/api` y `/ws` detrás del ALB o API Gateway.
12. Configurar health check en `/api/health` y alarmas de errores 4xx/5xx, CPU, memoria y desconexiones WebSocket.

## Actualizaciones y logs

Generar el APK Android de release:

```powershell
flutter build apk --release --dart-define=API_URL=https://DOMINIO/movimiento/api
```

El cliente usa WebSocket como canal principal (`/movimiento/ws` detrás del
proxy), guarda primero cada muestra en SQLite y reintenta las pendientes por
HTTP cuando no hay conectividad. La app no puede garantizar P95 menor de un
segundo: hay que reportar el valor real de `/api/metrics`, junto con red,
dispositivo, duración y porcentaje de muestras válidas.

```powershell
docker build -t movimiento-api:VERSION ./backend
docker tag movimiento-api:VERSION ID_ECR.dkr.ecr.REGION.amazonaws.com/movimiento-api:VERSION
docker push ID_ECR.dkr.ecr.REGION.amazonaws.com/movimiento-api:VERSION
```

Actualizar la task definition de ECS con la nueva imagen y hacer un deployment gradual. Revisar logs en CloudWatch y probar `/api/health` antes de anunciar la versión.

## Errores frecuentes

- **401:** token ausente, inválido o vencido.
- **403:** el usuario intenta acceder a un dispositivo que no le pertenece.
- **No aparece el celular:** revisar `API_URL`, IP LAN, firewall de Windows y que ambos equipos estén en la misma red.
- **Mapa sin mosaicos:** comprobar conectividad HTTPS y usar la atribución configurada para Carto/OpenStreetMap.
- **No se envían puntos:** comprobar login, consentimiento, permisos GPS y la cola local `ubicaciones_pendientes`.
- **WebSocket desconectado:** comprobar proxy/load balancer, timeout y la ruta `/ws` con `wss://` detrás de HTTPS.
