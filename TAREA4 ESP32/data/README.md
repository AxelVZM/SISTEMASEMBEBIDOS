# Datos locales

`vendors.sqlite3` contiene registros de asignaciones oficiales IEEE MA-L, MA-M y MA-S y Bluetooth SIG Company Identifiers. `vendors_manifest.json` conserva las URL, fecha de descarga, número de filas y SHA-256 de cada archivo fuente. La búsqueda usa el prefijo más específico: 36, 28 y luego 24 bits. No hay MAC de demostración en esta base.

Fuentes oficiales:
- https://standards.ieee.org/products-programs/regauth/
- https://www.bluetooth.com/specifications/assigned-numbers/
- Las cuatro URL de descarga exactas aparecen en el manifiesto.

La información registral y sus denominaciones pertenecen a sus respectivos titulares. Los registros se suministran para consulta local y conservan su procedencia; no se afirma que IEEE o Bluetooth SIG avalen este proyecto. El titular de un bloque o identificador de empresa puede ser un proveedor de componentes. No demuestra marca, tipo ni modelo de un producto final.

`name_rules.json` contiene expresiones extensibles para empresas y nombres anunciados; no contiene prefijos inventados. Redmi y POCO sólo se separan de Xiaomi si el nombre los anuncia. Los nombres permiten inferencias de confianza baja. El modelo comercial permanece no identificable. Las asignaciones IAB y CID no se usan como OUI.

Para actualizar con Internet:

```powershell
.\.venv\Scripts\python.exe scripts\update_vendors.py
```

Si un servidor no permite la descarga automatizada, descarga `oui.csv`, `mam.csv`, `oui36.csv` y `company_identifiers.yaml` desde las fuentes oficiales y ejecuta:

```powershell
.\.venv\Scripts\python.exe scripts\update_vendors.py --source-dir C:\registros
```

Una descarga incompleta no reemplaza la base existente. Reinicia el backend tras actualizar la base o editar reglas de nombres.

`observations.sqlite3`, `settings.json` y archivos WAL se generan al ejecutar el backend. Contienen información local de observación; no vienen precargados. La retención elimina observaciones antiguas y direcciones sin detecciones dentro del período configurado.

La descarga contiene 54 399 filas IEEE y 54 396 prefijos únicos. Las filas repetidas de los prefijos históricos 080030 y 0001C8 conservan todos los titulares, unidos mediante ` | `; no se elige arbitrariamente uno para inferir una marca. El manifiesto diferencia filas fuente y registros únicos.

`ble_appearance.json` contiene la tabla local de categorías/subcategorías Appearance de Bluetooth SIG (342 valores), su URL fuente y SHA-256. Se usa como declaración de tipo del emisor, sin autenticar marca o modelo; no requiere Internet para consultar.
