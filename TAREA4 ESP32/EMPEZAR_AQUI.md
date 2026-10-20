# Para ejecutar la versión EC2

**Empieza por README.md.** Incluye GitHub, servidor EC2, SSH/HTTPS, carga Arduino y puente USB Windows. `README_EC2_HTTPS.md` explica la publicación pública conservando las aplicaciones existentes.

El texto siguiente describe el firmware V7.2 y su antigua subida opcional a Lambda. Esa subida no se utiliza en el flujo EC2 por USB; no la actives para intentar conectar este servidor.

---

# Órbita V7.2 — contador embebido ESP32 con red opcional

Esta versión parte de tu V7 original. Conserva captura Wi-Fi/BLE, conteos separados en 60 segundos, la base IEEE completa, Company IDs Bluetooth, WPS/P2P, registro LittleFS, OLED, RTC, watchdog y ensayos. Integra configuración de red y subida opcional a AWS, sin credenciales grabadas en el código.

**El sistema cuenta direcciones observadas, no garantiza equipos físicos únicos. Conectarse a tu red no mejora automáticamente la recepción ni revela el modelo de un celular.** La red sirve para comprobar conectividad, obtener hora y enviar datos; para escuchar redes cercanas no necesita asociarse a ellas.

## Nuevo: clasificación automática de tipo

En el Explorador aparece **Tipo de equipo**, con filtro y explicación en Detalles. Se calcula en el ESP32 y también se incluye en el CSV y la instantánea enviada a AWS.

Categorías: teléfono/celular, laptop, computadora, tablet, router, punto de acceso, equipo de red, cañón/proyector, televisor, pantalla, impresora/escáner, cámara, audio, reloj/wearable, consola, almacenamiento/NAS, multimedia, periférico y sensor. Los equipos sin evidencia quedan **Sin determinar**.

- **Declarado; no autenticado:** tipo primario WPS/Wi-Fi Direct o Appearance BLE. Un teléfono genérico anunciado no demuestra que sea un celular; por eso la categoría se denomina teléfono/celular.
- **Posible; solo nombre:** una palabra del nombre o modelo sugiere una categoría. Puede equivocarse o ser un nombre elegido por el usuario. No tiene un porcentaje de precisión validado.
- **Rol observado:** se reciben tramas de AP. Esto permite reconocer un punto de acceso, pero no garantiza que sea un router físico: podría ser un hotspot de un teléfono o laptop.
- **Evidencia contradictoria:** las fuentes o anuncios discrepan; se evita asignar un tipo.

No se usa SSID, OUI, fabricante ni el bit MAC local/universal para deducir celular/laptop. Por ejemplo, la marca Canon no se interpreta como cañón/proyector. La clasificación no identifica al propietario, no vincula MAC aleatorias y no garantiza modelo exacto. No necesita registrar equipos ni instalar nada en los observados.

Los campos de clasificación del CSV quedan en la columna existente `fuente`, para conservar las 16 columnas y los registros anteriores. El filtro de tipo permite explorar las filas recibidas; no genera un conteo de equipos físicos únicos. En firmware anterior, sin esos campos, el nuevo panel muestra Sin determinar.

## 1. Cargar el programa en Windows

1. Extrae todo el ZIP en una carpeta nueva; no mezcles archivos de V7 y V7.2.
2. Abre `DetectorTiempoReal/DetectorTiempoReal.ino` en Arduino IDE.
3. En Gestor de placas instala **esp32 by Espressif Systems 3.3.2**. URL de instalación si te hace falta: https://espressif.github.io/arduino-esp32/package_esp32_index.json
4. Si tu placa es ESP32 clásico de 4 MB: selecciona **ESP32 Dev Module**, **Flash Size 4MB**, **Partition Scheme Huge APP (3MB No OTA/1MB SPIFFS)**, **PSRAM Disabled**, **Upload Speed 115200** y tu puerto COM. Mantén **Erase All Flash Before Sketch Upload: Disabled** para conservar ajustes y registros.
5. Pulsa Verificar y Subir. Ante `Wrong boot mode`, mantén BOOT durante `Connecting` y suéltalo cuando comience la escritura. Si hace falta, mantén BOOT, pulsa y suelta EN y vuelve a cargar.
6. Cierra el Monitor Serie. Abre `PanelTiempoReal.html` con Chrome o Edge y pulsa **Conectar ESP32**. Selecciona el COM.
7. Confirma **firmware 7.2** y espera al menos 60 segundos para llenar la ventana inicial.

Se compiló para ESP32 clásico con 3.3.2 y Huge APP. No se valida automáticamente para S2/S3/C3/C6: USB tipo C no identifica el chip. Las librerías utilizadas vienen con el paquete Espressif; no necesitas instalar otra librería de terceros.

## 2. Ingresar tu red sin editar el código

En **Resumen**, abre **Tu red Wi-Fi y nube · opcional**:

1. Ingresa el SSID exacto de tu red de **2,4 GHz** y su contraseña. Para una red abierta marca **Mi red no tiene contraseña**.
2. Deja desactivada **Activar subida automática a AWS** mientras pruebas.
3. Pulsa **Guardar en ESP32**. Los ajustes quedan en NVS y sobreviven a un reinicio.
4. Pulsa **Probar conexión**. La placa pausa la escucha, intenta conectarse durante un máximo aproximado de 8 segundos y vuelve a capturar. La prueba no envía observaciones a AWS.
5. El mensaje confirma éxito o indica revisar SSID, contraseña o cobertura.

Después de guardar, el campo de contraseña se vacía. Si vuelves a guardar la **misma red** dejando el campo vacío, se conserva la clave anterior. Para otra red necesitas proporcionar su clave o marcar red abierta. **Olvidar red** elimina la configuración activa y desactiva las subidas; conserva los CSV.

La contraseña no se devuelve en telemetría ni se guarda en el navegador. Se transmite por USB al configurar y queda en NVS; este proyecto no habilita cifrado de flash/NVS. No se promete borrado forense al olvidar la red.

## 3. Activar AWS si lo necesitas

El modo predeterminado funciona **sin red y sin nube**. Para habilitar la subida:

1. Despliega `Nube/lambda_despliegue.zip` siguiendo `Nube/LEEME_AWS.md`. No se ha cambiado tu cuenta ni desplegado nada desde esta entrega.
2. Comprueba que la URL HTTPS en el formulario sea tu API. Se propone la URL que venía en tus adjuntos, pero su funcionamiento no se ha comprobado en vivo.
3. Define el intervalo entre intentos: **60–3600 segundos**, con **300 segundos** por defecto.
4. Marca **Activar subida automática a AWS** y guarda. Al arrancar se concede una espera inicial de 30 segundos; al guardar se programa el próximo intento en unos 2 segundos, esperando a que termine cualquier fase BLE.
5. Consulta el resultado HTTP y el contador de envíos correctos en el panel. El registro local sigue funcionando aunque falle Internet.

La placa se conecta solo durante la operación y luego se desconecta para volver a recorrer canales. No mantiene una asociación permanente mientras salta por todas las redes.

**Las conexiones/subidas pausan Wi-Fi y BLE.** La pantalla muestra fase `Red`, la alerta de pausa y el estado de envío. La captura no es continua durante esa operación. Los conteos mantienen su ventana de 60 segundos y pueden decaer si no reciben tramas. Los ensayos afectados quedan marcados con incidencia. Para evaluar el conteo, desactiva AWS y espera la estabilización del ensayo.

Se valida HTTPS con Amazon Root CA 1; hace falta fecha válida obtenida por USB, RTC o SNTP. No se usa `setInsecure()`. La URL debe usar HTTPS; un servidor cuya cadena no sea compatible con esa CA no será aceptado.

Se envía una instantánea: total de clientes/AP observados en 60 segundos, hasta **24 clientes, 16 AP** priorizados por RSSI y **16 anuncios BLE**. Se limita el detalle para reservar RAM para TLS; las tablas locales siguen siendo de **96 Wi-Fi y 32 BLE**. Los totales pueden superar el detalle enviado. La nube no suma Wi-Fi y BLE como equipos únicos.

Cada reporte tiene su ID y el backend evita duplicar sus reintentos. Las subidas son instantáneas, no un respaldo completo del CSV: no hay cola persistente de subidas ni recuperación automática de snapshots fallidos. El registro flash sigue siendo la copia local disponible.

## 4. Qué información puede identificar

- **MAC universal:** titular del prefijo IEEE MA-L, MA-M o MA-S. No confirma necesariamente marca comercial ni modelo.
- **MAC local:** no se transforma ni se consulta como si fuera una MAC de fábrica. Puede ser aleatoria o asignada localmente; no demuestra que sea un celular.
- **WPS/Wi-Fi Direct:** nombre y fabricante/modelo publicados, cuando existen; quedan diferenciados del titular IEEE. Si hay contradicciones WPS, se marca el conflicto y no se envía esa marca/modelo como identificación válida a la nube.
- **BLE:** nombre anunciado, Company ID/SIG, Appearance y anuncio de servicio DIS, conservando los límites de V7. Anunciar DIS no implica que se haya leído un modelo.
- **AP:** se añaden a Detalles las capacidades de generación Wi-Fi y seguridad anunciadas por beacons/probe responses. No son una auditoría de seguridad ni verifican la autenticidad de los anuncios. No se identifica WEP únicamente por el bit de privacidad.

**No hay un método garantizado para obtener marca y modelo exactos de todos los celulares sin que publiquen información suficiente.** Tampoco se detecta cualquier electrónico por estar encendido: se reciben emisiones compatibles, Wi-Fi de 2,4 GHz en canales 1–11 y BLE.

## 5. Qué se conserva de V7

Conteos separados, filtros, CSV, historial USB, ensayos, demo aislada, OLED SSD1306, LED y DS3231 opcionales, watchdog, recuperación de radio, registro en dos segmentos y exportación USB con control de secuencia. Los CSV existentes `/registro_v7_*.csv` conservan su formato de 16 columnas. No se borra el registro al cambiar o eliminar la configuración de red.

La página USB mantiene su diseño y sus cuatro secciones. Solo se añade un bloque desplegable para la red y los campos nuevos de Detalles. `Nube/index.html` es el panel AWS complementario del otro adjunto; no reemplaza al panel principal ni hace falta para operar sin conexión.

## 6. Verificación

La compilación y las pruebas automatizadas están documentadas en `PRUEBAS.md`. Falta probar radio, memoria libre durante TLS, servidor real, estabilidad, consumo y accesorios sobre tu placa física. La campaña de latencia/colas/pérdidas sigue pospuesta.

Para montaje consulta `MONTAJE_Y_AUTONOMIA.md` y `CONEXIONES.svg`. Puedes usar solo ESP32 y cable; los accesorios son opcionales.
