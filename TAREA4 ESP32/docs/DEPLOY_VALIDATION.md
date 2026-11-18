# Verificación de la adaptación

- Suite original ejecutada con las dependencias de backend/requirements.txt y tests/requirements.txt: **111 pruebas aprobadas**, 1 aviso, sin fallos.
- Comparación byte a byte contra el ZIP adjunto: **42 archivos idénticos** en firmware/, backend/, frontend/ y data/. No se cambia lógica de captura, clasificación, protocolo ni interfaz.
- Los cuatro archivos binarios coinciden con los SHA256 del manifiesto original.
- `bash -n deploy/install-ec2.sh`: correcto.
- Sintaxis Python del supervisor: correcta mediante ast.parse.
- `git check-ignore`: excluye venv, observaciones, configuración, claves PEM y logs; conserva vendors.sqlite3 y los binarios precompilados.
- Búsqueda de formatos habituales de claves privadas/tokens AWS/GitHub: sin coincidencias. No se añaden credenciales reales.
- La instalación Nginx no se pudo ejecutar en el entorno de preparación por falta de privilegios de sistema; **no se afirma haber validado nginx -t, el túnel ni HTTP/WebSocket de extremo a extremo**. El instalador ejecuta nginx -t antes de recargar y el README incluye las comprobaciones reales de Host, API y WebSocket 101.
- No se probó carga física del ESP32, Programador de tareas de Windows, creación de EC2 ni publicación en GitHub: requieren tu hardware y cuentas. Los scripts PowerShell se revisaron, no se ejecutaron en Windows.
- No se despliega ni publica nada desde este paquete automáticamente. El acceso final depende de Security Group, IP correcta, clave SSH, PC activa, sesión iniciada y USB disponible.

Cambios: README.md, .gitignore, docs/README_ORIGINAL.md y nuevos archivos deploy/*. Se conserva el resto del proyecto original. El histórico requirements-lock.txt original no se emplea como lock del despliegue; se instala requirements.txt original.
