"""Class, type, and target classification (Celular y Tablet, Laptop, Smart TV, Audífonos, Impresora, Router, Cañón)."""

TARGET_CLASSES = ('Celular y Tablet', 'Laptop', 'Smart TV', 'Audífonos', 'Impresora', 'Router', 'Cañón')

# Celular y Tablet comparten una sola clase objetivo; el subtipo granular se conserva aparte.
MERGE = {'Celular': 'Celular y Tablet', 'Tablet': 'Celular y Tablet'}

CATEGORY_TO_TARGET = {
    'Celular': 'Celular y Tablet',
    'Teléfono': 'Celular y Tablet',
    'Teléfono inalámbrico': 'Celular y Tablet',
    'Equipo telefónico': 'Celular y Tablet',
    'Módem': 'Router',
    'Tablet': 'Celular y Tablet',
    'Tableta digitalizadora': 'Celular y Tablet',
    'Computadora de mano': 'Celular y Tablet',
    'Laptop': 'Laptop',
    'Computadora': 'Laptop',
    'Computadora convertible': 'Laptop',
    'Servidor': 'Laptop',
    'Smart TV': 'Smart TV',
    'Televisor': 'Smart TV',
    'Audífonos': 'Audífonos',
    'Manos libres': 'Audífonos',
    'Impresora': 'Impresora',
    'Impresora multifunción': 'Impresora',
    'Equipo de impresión': 'Impresora',
    'Equipo de imagen': 'Impresora',
    'Escáner': 'Impresora',
    'Router': 'Router',
    'Switch': 'Router',
    'Dispositivo de red': 'Router',
    'Cañón': 'Cañón',
    'Proyector': 'Cañón',
    'Pantalla': 'Cañón',
    'Videoconferencia': 'Cañón',
}

def classic_type(cod):
    if cod is None or cod & 3: return None
    major = (cod >> 8) & 31; minor = (cod >> 2) & 63
    category = None; detail = ''; specific = False
    if major == 1:
        category = {0: 'Computadora', 1: 'Computadora', 2: 'Servidor', 3: 'Laptop', 4: 'Computadora de mano', 5: 'Computadora de mano', 6: 'Computadora vestible', 7: 'Tablet'}.get(minor, 'Computadora'); specific = minor != 0
    elif major == 2:
        category = {0: 'Teléfono', 1: 'Celular', 2: 'Teléfono inalámbrico', 3: 'Celular', 4: 'Módem', 5: 'Equipo telefónico'}.get(minor, 'Teléfono'); specific = minor != 0
    elif major == 3:
        category = 'Dispositivo de red'
    elif major == 4:
        category = {0: 'Equipo audiovisual', 1: 'Audífonos', 2: 'Manos libres', 4: 'Micrófono', 5: 'Altavoz', 6: 'Audífonos', 7: 'Reproductor de audio', 8: 'Audio de vehículo', 9: 'Decodificador', 10: 'Equipo Hi-Fi', 11: 'Grabador de video', 12: 'Cámara', 13: 'Cámara', 14: 'Cañón', 15: 'Cañón', 16: 'Videoconferencia', 18: 'Equipo de videojuegos'}.get(minor, 'Equipo audiovisual'); specific = minor != 0
    elif major == 5:
        keyboard = bool(minor & 16); pointing = bool(minor & 32); kind = minor & 15
        category = 'Teclado y dispositivo apuntador' if keyboard and pointing else 'Teclado' if keyboard else 'Dispositivo apuntador' if pointing else {1: 'Joystick', 2: 'Control de videojuegos', 3: 'Control remoto', 4: 'Sensor', 5: 'Tableta digitalizadora', 6: 'Lector de tarjetas', 7: 'Lápiz digital', 8: 'Escáner', 9: 'Control gestual'}.get(kind, 'Dispositivo de entrada'); specific = minor != 0
    elif major == 6:
        capabilities = [name for bit, name in ((4, 'Cañón'), (8, 'Cámara'), (16, 'Escáner'), (32, 'Impresora')) if minor & bit]
        detail = ', '.join(capabilities)
        category = 'Impresora multifunción' if 'Impresora' in capabilities and len(capabilities) > 1 else 'Impresora' if 'Impresora' in capabilities else capabilities[0] if len(capabilities) == 1 else 'Impresora'; specific = bool(capabilities)
    elif major == 7:
        category = {1: 'Reloj', 2: 'Buscapersonas', 3: 'Chaqueta electrónica', 4: 'Casco electrónico', 5: 'Gafas electrónicas'}.get(minor, 'Dispositivo vestible'); specific = minor != 0
    elif major == 8:
        category = 'Juguete electrónico'
    elif major == 9:
        category = {1: 'Medidor de presión', 2: 'Termómetro', 3: 'Báscula', 4: 'Medidor de glucosa', 5: 'Oxímetro', 6: 'Sensor cardíaco'}.get(minor, 'Equipo de salud'); specific = minor in range(1, 7)
    if not category: return None
    return dict(category=category, specific=specific, detail=detail or f'major={major}, minor={minor}')

def wps_type(value):
    if not value: return None
    raw = bytes.fromhex(value)
    if len(raw) != 8 or raw[2:6] != b'\x00\x50\xf2\x04': return None
    major = int.from_bytes(raw[:2], 'big'); minor = int.from_bytes(raw[6:], 'big')
    broad = {1: 'Laptop', 2: 'Dispositivo de entrada', 3: 'Impresora', 4: 'Cámara', 5: 'Almacenamiento', 6: 'Router', 7: 'Cañón', 8: 'Reproductor multimedia', 9: 'Equipo de videojuegos', 10: 'Celular', 11: 'Equipo de audio'}
    specific = {
        (1, 1): 'Laptop', (1, 2): 'Servidor', (1, 3): 'Laptop', (1, 4): 'Laptop', (1, 5): 'Tablet', (1, 7): 'Tablet',
        (3, 1): 'Impresora', (3, 2): 'Impresora', (4, 1): 'Cámara', (5, 1): 'Almacenamiento de red',
        (6, 1): 'Router', (6, 2): 'Router', (6, 3): 'Router',
        (7, 1): 'Televisor', (7, 2): 'Cañón', (7, 3): 'Cañón',
        (9, 1): 'Consola', (9, 2): 'Consola', (9, 3): 'Consola',
        (10, 1): 'Celular', (10, 2): 'Celular', (10, 3): 'Celular', (10, 4): 'Celular', (10, 5): 'Celular',
    }
    category = specific.get((major, minor), broad.get(major))
    if not category: return None
    return dict(category=category, specific=(major, minor) in specific, detail=f'categoría={major}, subcategoría={minor}')

def ble_manufacturer_hint(company_id, hex_data='', tx_power=None):
    """Decode BLE Manufacturer Specific Data payloads and Company IDs into brand, category, and device model."""
    if company_id is None: return None
    raw = b''
    if hex_data:
        try: raw = bytes.fromhex(hex_data)
        except ValueError: raw = b''
    first = raw[0] if raw else None

    if company_id == 76:  # Apple, Inc.
        if first == 0x07:
            return dict(brand='Apple', category='Audífonos', target='Audífonos', device='Apple AirPods / Beats', detail='Apple Continuity Proximity Pairing (0x07)')
        if first == 0x0B:
            return dict(brand='Apple', category='Reloj inteligente', target='Otro', device='Apple Watch', detail='Apple Continuity Watch (0x0B)')
        if first == 0x0E:
            return dict(brand='Apple', category='Celular', target='Celular', device='Apple iPhone (Hotspot)', detail='Apple Continuity Tethering Source (0x0E)')
        if first == 0x0D or (tx_power is not None and 8 <= tx_power <= 9):
            return dict(brand='Apple', category='Tablet', target='Tablet', device='Apple iPad (Continuity)', detail='Apple Continuity iPad / Tethering (0x0D)')
        if first in (0x09, 0x0A) or (tx_power is not None and tx_power >= 10):
            return dict(brand='Apple', category='Laptop', target='Laptop', device='Apple MacBook (Continuity)', detail='Apple Continuity Mac / AirPlay')
        return dict(brand='Apple', category='Celular', target='Celular', device='Apple iPhone (BLE)', detail=f'Apple Continuity (0x{first:02X})' if first is not None else 'Apple BLE')

    if company_id == 6:  # Microsoft
        if first == 0x01 and len(raw) >= 2:
            dtype = raw[1] & 0x1F
            mapping = {
                0x0F: ('Microsoft', 'Laptop', 'Laptop', 'Laptop Windows (CDP)'),
                0x10: ('Microsoft', 'Tablet', 'Tablet', 'Tablet Windows Surface (CDP)'),
                0x09: ('Microsoft', 'Laptop', 'Laptop', 'PC / Laptop Windows (CDP)'),
                0x0C: ('Microsoft', 'Laptop', 'Laptop', 'Laptop Linux (CDP)'),
                0x0E: ('Microsoft', 'Cañón', 'Cañón', 'Microsoft Surface Hub (CDP)'),
                0x06: ('Apple', 'Celular', 'Celular', 'Apple iPhone (CDP)'),
                0x07: ('Apple', 'Tablet', 'Tablet', 'Apple iPad (CDP)'),
                0x08: ('Android', 'Celular', 'Celular', 'Celular Android (CDP)'),
                0x0B: ('Microsoft', 'Celular', 'Celular', 'Celular Windows (CDP)'),
            }
            if dtype in mapping:
                b, c, t, dev = mapping[dtype]
                return dict(brand=b, category=c, target=t, device=dev, detail=f'Microsoft CDP tipo 0x{dtype:02X}')
        elif first == 0x03 and len(raw) >= 5 and raw[1] == 0x01:
            cod = raw[2] | (raw[3] << 8) | (raw[4] << 16)
            decoded = classic_type(cod)
            if decoded:
                t = CATEGORY_TO_TARGET.get(decoded['category'], 'Laptop')
                return dict(brand='Microsoft', category=decoded['category'], target=t, device=f"{decoded['category']} Windows (Swift Pair)", detail=f"Microsoft Swift Pair CoD 0x{cod:06X}")
        return dict(brand='Microsoft', category='Laptop', target='Laptop', device='Laptop Windows (BLE)', detail='Microsoft BLE Beacon')

    company_map = {
        117: ('Samsung', 'Celular', 'Celular', 'Samsung Galaxy (BLE)'),
        224: ('Google', 'Celular', 'Celular', 'Google Pixel / Android (BLE)'),
        911: ('Xiaomi', 'Celular', 'Celular', 'Xiaomi / Redmi (MiBeacon)'),
        637: ('Huawei', 'Celular', 'Celular', 'Huawei (BLE)'),
        2670: ('Honor', 'Celular', 'Celular', 'Honor (BLE)'),
        216: ('Motorola', 'Celular', 'Celular', 'Motorola Moto (BLE)'),
        1850: ('OPPO', 'Celular', 'Celular', 'OPPO (BLE)'),
        2103: ('Vivo', 'Celular', 'Celular', 'Vivo (BLE)'),
        1839: ('OnePlus', 'Celular', 'Celular', 'OnePlus (BLE)'),
        301: ('Sony', 'Cañón', 'Cañón', 'Sony VPL / Proyector (BLE)'),
        196: ('LG', 'Cañón', 'Cañón', 'LG CineBeam / Proyector (BLE)'),
        58: ('Panasonic', 'Cañón', 'Cañón', 'Cañón Panasonic PT (BLE)'),
        34: ('NEC', 'Cañón', 'Cañón', 'Cañón NEC NP (BLE)'),
        64: ('Epson', 'Cañón', 'Cañón', 'Cañón / Impresora Epson (BLE)'),
        101: ('HP', 'Impresora', 'Impresora', 'Impresora HP (BLE)'),
        283: ('HP', 'Impresora', 'Impresora', 'Impresora HP LaserJet/Smart Tank (BLE)'),
        425: ('Canon', 'Impresora', 'Impresora', 'Impresora Canon PIXMA (BLE)'),
        1877: ('Brother', 'Impresora', 'Impresora', 'Impresora Brother (BLE)'),
        497: ('Zebra', 'Impresora', 'Impresora', 'Impresora Zebra (BLE)'),
        605: ('Lexmark', 'Impresora', 'Impresora', 'Impresora Lexmark (BLE)'),
        566: ('Ricoh', 'Impresora', 'Impresora', 'Impresora Ricoh (BLE)'),
        395: ('Konica Minolta', 'Impresora', 'Impresora', 'Impresora Konica Minolta (BLE)'),
        549: ('Lenovo', 'Laptop', 'Laptop', 'Laptop / Tablet Lenovo (BLE)'),
        455: ('Dell', 'Laptop', 'Laptop', 'Laptop Dell (BLE)'),
        461: ('ASUS', 'Laptop', 'Laptop', 'Laptop ASUS (BLE)'),
        496: ('Acer', 'Laptop', 'Laptop', 'Laptop Acer (BLE)'),
        2: ('Intel', 'Laptop', 'Laptop', 'Laptop con Bluetooth Intel'),
        93: ('Realtek', 'Laptop', 'Laptop', 'Laptop con Bluetooth Realtek'),
        539: ('Cisco', 'Router', 'Router', 'Router / AP Cisco (BLE)'),
        2383: ('MikroTik', 'Router', 'Router', 'Router MikroTik (BLE)'),
        1094: ('Netgear', 'Router', 'Router', 'Router Netgear (BLE)'),
    }
    if company_id in company_map:
        b, c, t, dev = company_map[company_id]
        if company_id == 117 and first == 0x42 and len(raw) >= 3 and (raw[2] & 0x04):
            return dict(brand='Samsung', category='Tablet', target='Tablet', device='Samsung Galaxy Tab (BLE)', detail='Samsung BLE Tablet')
        return dict(brand=b, category=c, target=t, device=dev, detail=f'Bluetooth SIG Company ID {company_id} ({b})')
    return None

PARENTS = {
    'Laptop': 'Computadora', 'Tablet': 'Computadora', 'Servidor': 'Computadora',
    'Computadora convertible': 'Computadora', 'Computadora de mano': 'Computadora',
    'Reloj inteligente': 'Reloj', 'Reloj deportivo': 'Reloj',
    'Celular': 'Teléfono', 'Equipo telefónico': 'Teléfono', 'Teléfono inalámbrico': 'Teléfono',
    'Router': 'Dispositivo de red', 'Switch': 'Dispositivo de red',
    'Impresora': 'Equipo de impresión', 'Impresora multifunción': 'Equipo de impresión', 'Escáner': 'Equipo de impresión',
    'Cañón': 'Pantalla', 'Proyector': 'Pantalla',
    'Audífonos': 'Equipo audiovisual', 'Altavoz': 'Equipo audiovisual'
}

def related(a, b):
    return a == b or PARENTS.get(a) == b or PARENTS.get(b) == a or (CATEGORY_TO_TARGET.get(a) and CATEGORY_TO_TARGET.get(a) == CATEGORY_TO_TARGET.get(b))
