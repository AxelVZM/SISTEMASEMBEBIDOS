# Actualización del panel

Se muestran direcciones observadas Wi-Fi y BLE por separado, sin total de equipos únicos. No hay reglas de asignación física por SSID. Se aclara que el SSID no identifica viviendas, negocios ni ubicaciones.

Los controles de servidor y red quedan dentro de «Configuración y conexiones · opcional», al final de la página y plegados al cargar. El conteo, estado y explorador conservan sus funciones.

## Aplicar en tu servidor sin consola local de Windows

1. Extrae el ZIP en Windows.
2. En la web de GitHub abre tu repositorio SISTEMASEMBEBIDOS y entra en la carpeta del proyecto desplegado (en tu servidor se llama TAREA4 ESP32).
3. En su carpeta web usa Add file → Upload files para reemplazar index.html por ESP32_EC2/web/index.html del ZIP. Confirma el cambio con Commit changes.
4. Opcional: reemplaza también PanelTiempoReal.html en la raíz de esa carpeta para actualizar la pantalla USB sin servidor. No cambies la estructura del repositorio.
5. En la consola web de AWS, ejecuta desde la carpeta del proyecto:

```bash
cd "$HOME/SISTEMASEMBEBIDOS/TAREA4 ESP32"
git pull --ff-only
bash despliegue/actualizar.sh
```

Si git informa cambios locales o conflictos, detente y conserva esa salida; no uses reset --hard.

6. Abre https://18.191.113.248/esp32/ y actualiza con Ctrl+F5. El apartado de token está ahora al final, dentro de Configuración y conexiones. Vuelve a conectar el USB si el navegador lo solicita.

No es necesario volver a cargar el firmware. No se cambian el token, la base de datos ni la configuración HTTPS. No se ha aplicado esta actualización a tu EC2 desde esta conversación.
