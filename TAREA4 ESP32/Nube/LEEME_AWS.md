> Complemento legado de Lambda/DynamoDB, conservado como código anterior. Para EC2 utiliza `README.md` en la raíz; no necesitas desplegar esta Lambda ni usar su URL.

# Complemento AWS de Órbita V7.1

No necesitas nube para usar la captura, la pantalla USB o el registro local. Este complemento reutiliza la arquitectura y el panel AWS adjuntos por ti; no sustituye al firmware V7.1.

## Despliegue

1. En tu Lambda existente carga `lambda_despliegue.zip`, con sus archivos en la raíz. Usa Python 3.12 o un runtime compatible y controlador `lambda_function.lambda_handler`. boto3 viene en el runtime de Lambda.
2. Conserva/crea la tabla DynamoDB `RegistroESP32`, con clave de partición de texto `id_registro`, sin clave de ordenación. Si usas otra equivalente, define `TABLA_DYNAMODB`.
3. El rol Lambda necesita `dynamodb:PutItem` y `dynamodb:Scan` sobre la tabla y permisos de logs. Activa TTL en el atributo numérico `expira`; la retirada prevista es tras siete días y la eliminación de DynamoDB puede demorarse.
4. Define `SAL_ALIAS` con al menos 32 caracteres aleatorios. Por ejemplo, genera una con `python -c "import secrets; print(secrets.token_hex(32))"`. Conserva su valor entre despliegues: cambiarla cambia los alias. Sin una sal válida las vistas que generan alias devuelven error.
5. Configura la API con GET, POST y OPTIONS hacia esa Lambda. En el panel USB escribe la URL HTTPS de esa API, configura tu Wi-Fi y habilita la subida.
6. Para abrir el panel remoto usa este `index.html` con Internet. Su `API_URL` conserva la URL del adjunto original. Actualízala si cambias de API. El panel carga Tailwind/Chart.js desde CDN.

No se ha ejecutado el despliegue ni se ha llamado a tu API durante la elaboración. Se mantiene el esquema de acceso del adjunto: CORS por defecto `*`, configurable con `ORIGEN_PANEL`. CORS no autentica usuarios; no se implementa aquí autenticación adicional de API.

## Datos y significado

- El ESP32 envía una instantánea de direcciones recibidas en los últimos 60 segundos, aunque el envío se realice cada varios minutos.
- Clientes y AP se separan. Una fila con roles AP/cliente se presenta como AP en la nube para evitar duplicarla entre esas dos listas; el conteo local conserva los roles de V7.
- El detalle está limitado a 24 clientes y 16 AP priorizados por RSSI. El total puede ser mayor que el listado: el truncamiento del detalle no permite calcular la proporción local/universal de todos los emisores.
- Para no sumar repetidamente los contadores acumulados de V7, el campo heredado `paquetes` de cada cliente vale 1 por reporte en que se envía esa MAC. En este panel representa reportes con observación, no tramas de radio. Las recepciones reales siguen disponibles en el panel USB y CSV de la placa.
- Hasta 16 anuncios BLE y `ble_total` se guardan por separado en DynamoDB. El panel AWS adjunto visualiza Wi-Fi/AP; la exploración y el conteo BLE completos permanecen en `PanelTiempoReal.html`. No se suman ambos protocolos como equipos únicos.
- Los alias son HMAC de una MAC observada con la sal configurada; no recuperan MAC de fábrica ni enlazan direcciones aleatorias diferentes. Los registros conservan MAC originales. El panel devuelve alias de clientes y muestra BSSID/SSID de AP.
- Marca/modelo WPS se muestran como anunciados, no autenticados. IEEE devuelve titular del bloque y nunca resuelve una MAC local como si fuera universal.
- La distancia del panel AWS sigue siendo un modelo RSSI sujeto a calibración; no determina el local físico ni metros exactos. El panel USB conserva la decisión de V7 de mostrar RSSI sin atribuir distancia.

El backend heredado consulta DynamoDB con `Scan` y paginación; es una solución pequeña de prototipo. No se ha realizado una prueba de escala/coste ni se presenta como una arquitectura de consultas indexadas.

## Base IEEE

Se reconstruyó `oui.txt.gz` a partir de los **54 220 prefijos** del V7 que adjuntaste: MA-L, MA-M y MA-S, con búsqueda por el prefijo más específico. Se conserva su manifiesto, que declara recuperación el 19 de octubre de 2026. No se afirma haber descargado ni verificado de nuevo esas fuentes en esta sesión.

Para futuras actualizaciones, ejecuta `python actualizar_ieee.py` desde esta carpeta con acceso a los CSV oficiales de IEEE. El script solo reemplaza la base si descarga y valida los tres registros. Después reconstruye el ZIP con los tres archivos de `backend/` en su raíz y vuelve a cargarlo en Lambda.

Para reconstruir el ZIP desde la raíz del proyecto con Python:

```python
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
base = Path('Nube')
with ZipFile(base / 'lambda_despliegue.zip', 'w', ZIP_DEFLATED) as z:
    for nombre in ('lambda_function.py', 'oui.txt.gz', 'ieee_fuentes.json'):
        z.write(base / 'backend' / nombre, nombre)
```
