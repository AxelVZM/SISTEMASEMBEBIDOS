# Identificación y Clasificación 2.2.0

Se amplía el motor de identificación y clasificación para detectar el **dispositivo específico (`detected_device`)**, la **marca (`brand` / `detected_brand`)** y clasificar cada observación dentro de las **6 categorías objetivo**:

1. **Celular** (Smartphones Android/iOS, hotspots móviles, equipos telefónicos)
2. **Tablet** (iPad, Galaxy Tab, MatePad, Redmi Pad, Surface Pro/Go, tablets Android/Windows)
3. **Laptop** (MacBook, ThinkPad, IdeaPad, Pavilion, EliteBook, Inspiron, Latitude, ZenBook, VivoBook, Nitro, Aspire, laptops Windows con CDP/Swift Pair o tarjeta Wi-Fi de PC)
4. **Impresora** (Impresoras y multifuncionales Wi-Fi Direct / BLE / Classic: HP LaserJet/DeskJet/OfficeJet/Smart Tank, Epson EcoTank/WorkForce, Canon PIXMA/MAXIFY, Brother, Xerox, Ricoh, Kyocera, Zebra, Lexmark, Konica Minolta)
5. **Router** (Enrutadores Wi-Fi, puntos de acceso, ONT/GPON y sistemas Mesh: TP-Link Archer/Deco, MikroTik RouterBOARD/hAP, Ubiquiti UniFi, Cisco/Meraki, Huawei, ZTE ZXHN, D-Link, Tenda, Mercusys, Netgear, Aruba, Fortinet, Arris, MitraStar, Hitron)
6. **Cañón** (Proyectores multimedia: Epson PowerLite/BrightLink/EB-/EF-, BenQ, Optoma, ViewSonic, Sony VPL, Panasonic PT-, NEC NP-, InFocus, LG CineBeam, Samsung The Freestyle, XGIMI, Wanbo, Vivitek, Christie)

## Fuentes combinadas en 2.2.0

- **IEEE MA-S/MA-M/MA-L (`data/vendors.sqlite3`)**: 54 396 prefijos OUI oficiales y 4 065 identificadores Bluetooth SIG. Se distingue proveedor de chip de radio (`Intel`, `Realtek`, `Qualcomm`, `MediaTek`, `Broadcom`, `Espressif`, `AzureWave`, `Lite-On`) de la marca comercial, y se utiliza el perfil de fabricante/radio para clasificar en `Laptop`, `Router`, `Impresora`, `Cañón`, `Tablet` o `Celular` cuando no se anuncia clase explícita.
- **Protocolos de fabricante BLE (`company_id` + `manufacturer_data`)**:
  - **Apple Continuity (`0x004C`)**: distingue iPhone/Hotspot (`0x0E`), iPad/Mac Tethering (`0x0D`), AirPods/Beats (`0x07`), Apple Watch (`0x0B`) y anuncios Continuity (`0x05`, `0x09`, `0x0C`, `0x0F`, `0x10`).
  - **Microsoft CDP (`0x0006`, tipo `0x01`) y Swift Pair (`0x03`)**: identifica directamente Laptops Windows (`0x0F`), Tablets Windows (`0x10`), PCs (`0x09`), iPhone (`0x06`), iPad (`0x07`), Android (`0x08`) y decodifica CoD embebido en Swift Pair.
  - **BLE de Impresoras y Proyectores**: reconoce anuncios de Seiko Epson (`64`), HP (`101`/`283`), Canon (`425`), Brother (`1877`), Zebra (`497`), Lexmark (`605`) y servicios Bluetooth de impresión (`0x1118`, `0x1119`, `0x1120`, `0x1122`, `0x1123`).
- **Bluetooth Classic CoD y BLE Appearance (`data/ble_appearance.json`)**: mapea directamente subtipos de `Celular`, `Tablet`, `Laptop`, `Impresora`, `Router` y `Cañón` (Appearance `0x0A03` Projector -> `Cañón`).
- **Metadatos Wi-Fi 802.11 (`firmware/main/wifi_metadata.c`)**:
  - Extrae atributos WPS `0x1011` (`wps_device_name`), `0x1021` (`wps_manufacturer`), `0x1023` (`wps_model_name`), `0x1024` (`wps_model_number`) y `0x1054` (`wps_primary_device_type`, incluyendo `(7,3)` -> `Cañón`, `(3,1)` -> `Impresora`, `(6,2)` -> `Router`, `(10,1)` -> `Celular`).
  - En tramas de Punto de Acceso (`Beacon` y `Probe Response`), extrae el `SSID` anunciado (`IE 0`), permitiendo identificar impresoras Wi-Fi Direct (`DIRECT-xx-HP...`, `DIRECT-xx-EPSON...`), cañones multimedia (`EPSON_Projector`, `PANASONIC-PJ`), routers (`TP-Link_...`, `MOVISTAR_...`, `CLARO_...`, `WIN_...`) y hotspots móviles sin inspeccionar SSIDs buscados por clientes en `Probe Request`.
- **Panel de Clasificación Objetivo (`frontend/`)**:
  - Tarjetas interactivas en tiempo real para **Celular, Tablet, Laptop, Impresora, Router y Cañón**, filtro rápido por clasificación (`#targetClass`), columnas enriquecidas con insignia de clasificación, dispositivo detectado y marca detectada, gráfico de barras de las 6 categorías y exportación CSV/JSON ampliada.
