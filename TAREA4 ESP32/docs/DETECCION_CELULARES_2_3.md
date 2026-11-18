# Detección de celulares 2.3.0

Los celulares actuales (Android 10+, iOS 14+) usan **MAC aleatoria**, por lo que la consulta OUI no da marca. Se añaden fuentes que sí la revelan:

| Fuente | Dónde | Qué aporta |
|---|---|---|
| Wi-Fi Direct (P2P) Device Info en *probe requests* | firmware `wifi_metadata.c` | Nombre del equipo (p. ej. `Galaxy A54`) y tipo WPS `10-x` = Celular |
| OUIs de IEs de fabricante (`vendor_ies`) en sondeos/asociación | firmware + `identify.py` | Apple `0017F2`, Samsung `0000F0`, Huawei `00E0FC`; P2P `506F9A09` (Android); chip Broadcom/MediaTek/Qualcomm/Realtek |
| Códigos de modelo → nombre comercial | `data/phone_models.json` | `SM-A546E` → Galaxy A54 5G, `iPhone14,7` → iPhone 14, `XT2343` → moto g54, `2201117TG` → Redmi Note 11 |
| mDNS unicast en la red local | `network_scanner.py` | Hostname (`Pams-iPhone`) y modelo TXT si el equipo lo publica |

## Cuándo el celular entrega marca/modelo

- **Bluetooth visible**: abrir *Ajustes → Bluetooth* deja al celular descubrible y anuncia su nombre (`Galaxy A54`, `Redmi Note 13`).
- **Wi-Fi Direct / Compartir cercano / Smart View** abiertos: envía P2P con nombre y tipo.
- **Misma red Wi-Fi que la PC**: hostname por mDNS (iPhone) o DNS inverso del router.
- Si nada de eso ocurre, solo se puede clasificar como *Celular* con marca probable por IE de fabricante; el modelo exacto no se transmite.

## Laptops y tablets (2.3.1)

- `data/device_models.json` (reemplaza `phone_models.json`) traduce también identificadores Apple: `MacBookPro18,3` → MacBook Pro 14" (M1 Pro, 2021), `Mac15,12` → MacBook Air 13" (M3), `iPad13,18` → iPad (10.ª gen.). Se obtienen por mDNS cuando el equipo está en la misma red.
- iPad en red local ya no se confunde con iPhone (ambos abren el puerto 62078).
- Laptops Windows: el modelo exacto **no se transmite** por radio ni por la red sin un agente instalado; se identifican como Laptop por nombre (`LAPTOP-XXXX`, `VivoBook-…`), clase Bluetooth o SMB.

## Tabla reorganizada

Vista simple: Tipo · Marca · Modelo (código debajo) · Nombre visible · Detectado por (y cómo) · Señal/distancia · Certeza · Última vez. «Vista técnica» añade MAC, rol, canal, primera detección y observaciones. El detalle se agrupa en Resumen, Señal y distancia, Actividad y Datos técnicos. CSV/JSON exportan todos los campos, más `certainty`, `how_identified` y `source`.

| Certeza | Significado |
|---|---|
| Alta | El equipo anunció su código o modelo |
| Media | Marca reconocida por su nombre o por la firma del fabricante |
| Baja | Estimado por el tipo de señal |

## Columna MAC y prefijos reales (2.3.2)

- La tabla muestra la MAC fija, junto a «Detectado por» (ya no solo en vista técnica).
- Reglas por prefijo (`data/device_models.json` → `prefixes`): la **marca** la fija el prefijo del fabricante, por lo que es 100% real. Solo se afirma la serie/línea comprobable, nunca el modelo exacto; la certeza queda en **Media** y el origen es «Serie por prefijo del fabricante».
  - `SM-A5xx` → Samsung Galaxy A (serie 50) · `CPH####` → OPPO (serie CPH) · `RMX####` → Realme (serie RMX) · `XT####` → Motorola moto (serie XT) · `TA-####` → Nokia/HMD · `SM-[TXP]###` → Galaxy Tab.
  - Si un código no coincide con ninguna regla, no se inventa marca ni modelo.

## Clases objetivo y estética (2.4.0)

- La clasificación objetivo ahora tiene 7 clases: **Celular y Tablet** (fusionadas en una), **Laptop**, **Smart TV**, **Audífonos**, **Impresora**, **Router**, **Cañón**. El subtipo granular (Celular vs Tablet) se conserva en `category`/`device_type` y se muestra como detalle.
- **Smart TV**: por nombre/SSID (Smart TV, BRAVIA, Tizen, WebOS, Roku TV, Fire TV) o tipo WPS televisor. Una palabra de tipo explícita pesa más que la categoría implícita de la marca.
- **Audífonos**: por Bluetooth (clase CoD de audio, AirPods/Beats por Continuity, nombres como AirPods).
- Interfaz: paleta ampliada en claro y oscuro (verde, ámbar, rosa, cian, violeta) con una insignia de color por tipo; el aviso de modo híbrido es una lista; «Chavito's Servicios» aparece en la barra lateral.
