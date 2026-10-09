# Movimiento GPS (TAREA3)

Seguimiento GPS en tiempo real (< 1 s) con app Android (Flutter), API REST en
Node.js y PostgreSQL, desplegado en AWS EC2.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `lib/` | App Flutter: GPS, podómetro, validación de puntos y envío por POST |
| `lib/servicios/filtro_gps.dart` | Decide qué lectura GPS se muestra (sin inventar puntos) |
| `lib/servicios/detector_pasos.dart` | Podómetro con el acelerómetro |
| `lib/servicios/seguimiento_remoto.dart` | Cliente de la API (POST/GET, keep-alive, cola offline) |
| `android/` | Proyecto Android (permisos, pantalla encendida durante el recorrido) |
| `test/` | Pruebas del filtro GPS y del podómetro |
| `backend/server.js` | API REST + WebSocket del panel |
| `backend/db.js` | PostgreSQL: esquema y escritura por lotes |
| `backend/public/index.html` | Panel web en tiempo real |
| `backend/*.py` | Scripts de instalación y despliegue en la EC2 |

## Compilar e instalar la app

```powershell
flutter build apk --release
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r build\app\outputs\flutter-apk\app-release.apk
```

## Mapas

Se elige con el botón de capas (app) o el selector arriba a la derecha (panel):

| Mapa | Clave | Zoom con imagen real |
| --- | --- | --- |
| Satélite / Satélite + calles (Esri) | No | 19 |
| Calles (OpenStreetMap) | No | 19 |
| CARTO Voyager | Incluida | 18 |
| MapTiler Satélite HD (por defecto) | Incluida | 20 |
| MapTiler Calles | Incluida | 20 |

**Cambiar la clave de MapTiler:** https://cloud.maptiler.com → **API keys**. Luego:

- App: `flutter build apk --release --dart-define=MAPTILER_KEY=nueva_clave`
- Panel: `const MAPTILER_KEY` en `backend/public/index.html`.

## Pruebas

```powershell
flutter test
```

## Servidor

Ver [README_DEPLOY_AWS.md](README_DEPLOY_AWS.md).
