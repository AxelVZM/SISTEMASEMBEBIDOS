import json, re, sqlite3
from pathlib import Path
from functools import lru_cache
from .device_types import classic_type, wps_type, related, ble_manufacturer_hint, TARGET_CLASSES, CATEGORY_TO_TARGET, MERGE

CHIPS = re.compile(r'\bIntel\b|Qualcomm|Atheros|Broadcom|MediaTek|Espressif|Realtek|Marvell|AzureWave|Lite.?On|LG Innotek', re.I)
PC_RADIO_CHIPS = re.compile(r'\bIntel\b|AzureWave|Lite.?On|Realtek|Marvell', re.I)
MOBILE_RADIO_CHIPS = re.compile(r'Qualcomm|Atheros|MediaTek|Broadcom|LG Innotek', re.I)
RANK = {'Desconocida': 0, 'Baja': 1, 'Media': 2, 'Alta': 3}

SERVICES = {
    '1101': 'Puerto serial (SPP)',
    '1108': 'Auricular (HSP)',
    '110B': 'Receptor de audio (A2DP)',
    '110E': 'Control remoto AV (AVRCP)',
    '1118': 'Impresión directa (BPP)',
    '1119': 'Impresión por referencia (BPP)',
    '111E': 'Manos libres (HFP)',
    '1120': 'Objetos de impresión directa',
    '1122': 'Impresión básica (BPP)',
    '1123': 'Estado de impresión (BPP)',
    '1124': 'Dispositivo de interfaz humana (HID)',
    '1800': 'Acceso genérico',
    '1801': 'Atributos genéricos',
    '180A': 'Información de dispositivo',
    '180D': 'Frecuencia cardíaca',
    '180F': 'Batería',
    '1812': 'Interfaz humana (HID)',
    '1816': 'Ciclismo',
    '1818': 'Potencia de ciclismo',
    '181C': 'Datos de usuario',
    '1826': 'Equipo de entrenamiento',
    '1844': 'Control de volumen',
    '184E': 'Control de flujo de audio',
    '1850': 'Capacidades de audio publicadas',
    'FD5A': 'Samsung SmartThings / Galaxy',
    'FD69': 'Samsung Continuity / Galaxy',
    'FD6F': 'Notificación de exposición (Celular)',
    'FD87': 'Motorola Mobility',
    'FDEE': 'Huawei Share',
    'FDF7': 'Servicio BLE HP',
    'FE2C': 'Google Fast Pair',
    'FE78': 'Impresora HP BLE',
    'FE95': 'Xiaomi MiBeacon',
    'FEAA': 'Google Eddystone',
    'FEF3': 'Google Quick Share / Nearby',
}
PRINT_SERVICES = {'1118', '1119', '1120', '1122', '1123', 'FE78', 'FDF7'}
PHONE_SERVICES = {
    'FD6F': (None, 'Celular', 'Notificación de exposición COVID (Smartphone)'),
    'FE2C': ('Google', 'Celular', 'Google Fast Pair (Android)'),
    'FEF3': ('Google', 'Celular', 'Google Quick Share / Nearby (Android)'),
    'FE95': ('Xiaomi', 'Celular', 'Xiaomi MiBeacon'),
    'FD5A': ('Samsung', 'Celular', 'Samsung Galaxy SmartThings'),
    'FD69': ('Samsung', 'Celular', 'Samsung Galaxy Continuity'),
    'FDEE': ('Huawei', 'Celular', 'Huawei Share'),
    'FD87': ('Motorola', 'Celular', 'Motorola BLE'),
}

# Vendor-specific IE OUIs (+type) in 802.11 probe/association requests: client fingerprint when the MAC is random.
# brand=None means chip/protocol evidence only (category hint, no commercial brand).
VENDOR_IES = {
    '0017F2': ('Apple', 'Celular', 'Baja', 'IE propietario Apple en sondeo Wi-Fi (iPhone/iPad/Mac)'),
    '0000F0': ('Samsung', 'Celular', 'Media', 'IE propietario Samsung en sondeo Wi-Fi (Galaxy)'),
    '00E0FC': ('Huawei', 'Celular', 'Media', 'IE propietario Huawei en sondeo Wi-Fi'),
    '506F9A09': (None, 'Celular', 'Baja', 'Búsqueda Wi-Fi Direct (P2P), típica de Android'),
}
VENDOR_CHIPS = {'001018': 'Broadcom', '00904C': 'Broadcom', '000CE7': 'MediaTek', '00A0C6': 'Qualcomm', '00037F': 'Qualcomm Atheros', '00E04C': 'Realtek'}

class Identifier:
    def __init__(self, data: Path):
        self.path = (data / 'vendors.sqlite3').resolve(); self.last_error = ''
        try: self.rules = json.loads((data / 'name_rules.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as error: self.rules = {}; self.last_error = 'Reglas no disponibles: ' + str(error)
        for key in ('organizations', 'names', 'categories'): self.rules.setdefault(key, [])
        self.vendor_defaults = self.rules.get('vendor_defaults', {})
        registry = data / 'ble_appearance.json'
        if not registry.exists(): registry = Path(__file__).resolve().parents[1] / 'data/ble_appearance.json'
        try: self.appearance = json.loads(registry.read_text(encoding='utf-8'))['entries']
        except (OSError, ValueError, KeyError): self.appearance = {}
        models = data / 'device_models.json'
        if not models.exists(): models = Path(__file__).resolve().parents[1] / 'data/device_models.json'
        try:
            raw = json.loads(models.read_text(encoding='utf-8'))
            self.phone_models = [v for k, v in raw.items() if not k.startswith('_') and k != 'prefixes']
            self.model_prefixes = raw.get('prefixes', [])
        except (OSError, ValueError): self.phone_models = []; self.model_prefixes = []

    def resolve_model(self, text):
        """Resolve a model code: exact code -> commercial name (certain); else brand prefix -> brand + provable series only."""
        if not text: return None
        # 1) Exact code match: the full commercial name is certain.
        for group in self.phone_models:
            m = re.search(group['pattern'], text, re.I)
            if not m: continue
            key = next((k for k in group['map'] if k.casefold() == m.group(1).casefold()), None)
            commercial = group['map'].get(key) if key else None
            if commercial:
                brand = next((r['brand'] for r in self.rules['names'] if re.search(r['pattern'], commercial, re.I)), None)
                return dict(brand=brand or group['brand'], category=group['category'], commercial=commercial, family='', code=m.group(0))
        # 2) Manufacturer prefix: the brand is determined by the prefix (100% real); series is the most we can assert.
        for rule in self.model_prefixes:
            m = re.search(rule['pattern'], text, re.I)
            if m:
                return dict(brand=rule['brand'], category=rule['category'], commercial='', family=rule['family'], code=m.group(0))
        # 3) Non-prefix group with a code but no exact name: assert brand only.
        for group in self.phone_models:
            if group.get('strict'): continue
            m = re.search(group['pattern'], text, re.I)
            if m:
                return dict(brand=group['brand'], category=group['category'], commercial='', family='', code=m.group(0))
        return None

    @lru_cache(maxsize=8192)
    def lookup(self, mac):
        if not self.path.exists(): return None
        compact = mac.replace(':', '')
        try:
            with sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True) as db:
                for length in (9, 7, 6):
                    row = db.execute('select organization,registry from oui where prefix=?', (compact[:length],)).fetchone()
                    if row: return dict(organization=row[0], registry=row[1], prefix=compact[:length])
        except sqlite3.Error as error: self.last_error = 'Base de fabricantes no disponible: ' + str(error)
        return None

    def brand_for(self, text):
        if not text or CHIPS.search(text): return None
        return next((rule['brand'] for rule in self.rules['organizations'] if re.search(rule['pattern'], text, re.I)), None)

    def identify(self, obs):
        result = dict(
            brand='Desconocido', commercial_brand='Desconocido', detected_brand='Desconocido',
            model='No identificable', detected_device='Dispositivo no identificado',
            category='Desconocido', device_type='Desconocido',
            classification='Sin clasificar', target_class='Sin clasificar', is_target_class=False,
            confidence='Desconocida', brand_confidence='Desconocida', category_confidence='Desconocida',
            model_confidence='Desconocida', role_confidence='Desconocida', classification_confidence='Desconocida',
            classification_source='Sin evidencia suficiente',
            network_role='Desconocido', organization='Desconocido', radio_vendor='No identificable',
            device_manufacturer='No identificable', company_identifier_owner='Desconocido',
            model_source='No disponible', evidence=[], warnings=[],
            field_evidence={'brand': [], 'category': [], 'model': [], 'network_role': []},
            advertised_capabilities=[], category_detail=''
        )
        brands = []; types = []
        def evidence(field, text): result['evidence'].append(text); result['field_evidence'][field].append(text)
        def brand(value, source, priority, confidence):
            if value: brands.append(dict(value=value, source=source, priority=priority, confidence=confidence)); evidence('brand', source)
        def dtype(category, source, priority, confidence, detail='', specific=False):
            if category and category != 'Desconocido': types.append(dict(value=category, source=source, priority=priority, confidence=confidence, detail=detail, specific=specific)); evidence('category', source)

        private = (obs.tech == 'wifi' and bool(int(obs.mac[:2], 16) & 2)) or (obs.tech == 'ble' and obs.address_type != 'public')
        result['private_address'] = private
        oui = self.lookup(obs.mac) if not private else None
        if private:
            result['warnings'].append('MAC posiblemente aleatoria o administrada localmente; BLE de tipo desconocido se trata como privado. No se consulta OUI ni se enlazan rotaciones.')
        elif oui:
            owner = oui['organization']; result['organization'] = owner
            text = f"IEEE {oui['registry']} {oui['prefix']}: {owner}; titular del bloque."
            if CHIPS.search(owner):
                result['radio_vendor'] = owner
                result['warnings'].append('El OUI identifica al proveedor de radio/módulo.')
            if ' | ' in owner:
                result['warnings'].append('Prefijo con múltiples titulares en el registro oficial.')
            else:
                brand(self.brand_for(owner), text, 50, 'Media')
            if text not in result['evidence']: result['evidence'].append(text)

        if obs.company_id is not None and self.path.exists():
            try:
                with sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True) as db:
                    row = db.execute('select name from companies where id=?', (obs.company_id,)).fetchone()
                if row:
                    result['company_identifier_owner'] = row[0]
                    src_cid = f'Bluetooth SIG Company ID {obs.company_id}: {row[0]}'
                    result['evidence'].append(src_cid)
                    cid_brand = self.brand_for(row[0])
                    if cid_brand:
                        brand(cid_brand, src_cid, 42, 'Media')
            except sqlite3.Error as error:
                self.last_error = 'Company Identifiers no disponibles: ' + str(error)

        ble_hint = ble_manufacturer_hint(obs.company_id, getattr(obs, 'manufacturer_data', ''), getattr(obs, 'tx_power', None))
        if ble_hint:
            hint_src = f"Datos de fabricante BLE ({ble_hint['detail']})"
            if ble_hint.get('brand'):
                brand(ble_hint['brand'], hint_src, 45, 'Media')
            if ble_hint.get('category'):
                dtype(ble_hint['category'], hint_src, 55, 'Media', ble_hint['detail'], specific=True)

        if obs.wps_manufacturer:
            result['device_manufacturer'] = obs.wps_manufacturer
            source = 'Fabricante autodeclarado en WPS/UPnP: ' + obs.wps_manufacturer
            wps_b = self.brand_for(obs.wps_manufacturer) or next((r['brand'] for r in self.rules['names'] if re.search(r['pattern'], obs.wps_manufacturer, re.I)), None)
            brand(wps_b, source, 80, 'Media')
            if source not in result['evidence']: result['evidence'].append(source)

        wps_model_text = ' '.join(filter(None, [obs.wps_model_name, obs.wps_model_number, getattr(obs, 'wps_device_name', '')])).strip()
        if wps_model_text:
            wps_src = 'Modelo/dispositivo autodeclarado en WPS/Red: ' + wps_model_text
            for rule in self.rules['names']:
                if re.search(rule['pattern'], wps_model_text, re.I):
                    brand(rule['brand'], wps_src, 75, 'Media')
                    if rule.get('category'): dtype(rule['category'], wps_src, 75, 'Media', specific=True)
                    break
            for rule in self.rules['categories']:
                if re.search(rule['pattern'], wps_model_text, re.I):
                    dtype(rule['category'], wps_src, 75, 'Media', specific=True)
                    break

        vendor_ies = [x for x in (getattr(obs, 'vendor_ies', '') or '').split(',') if x]
        for tag in vendor_ies:
            hit = VENDOR_IES.get(tag) or VENDOR_IES.get(tag[:6])
            if hit and obs.role != 'ap':
                v_brand, v_cat, v_conf, v_desc = hit
                v_src = f'{v_desc} [{tag}]'
                if v_brand: brand(v_brand, v_src, 46, 'Media')
                dtype(v_cat, v_src, 50 if v_brand else 45, v_conf, v_desc, specific=True)
            elif tag[:6] in VENDOR_CHIPS and result['radio_vendor'] == 'No identificable':
                result['radio_vendor'] = VENDOR_CHIPS[tag[:6]]
                result['evidence'].append(f'IE de fabricante de chip en sondeo Wi-Fi: {VENDOR_CHIPS[tag[:6]]} [{tag}]')

        resolved = None
        for text, label, priority in ((' '.join(filter(None, [obs.wps_model_name, obs.wps_model_number])), 'Modelo WPS/Red', 85),
                                      (getattr(obs, 'wps_device_name', ''), 'Nombre WPS/Red', 70), (obs.name, 'Nombre anunciado', 60)):
            resolved = self.resolve_model(text)
            if resolved:
                exact = bool(resolved['commercial'])
                conf = 'Alta' if exact else 'Media'
                detail = resolved['commercial'] or (f"{resolved['brand']} {resolved['family']}" if resolved['family'] else resolved['code'])
                r_src = f"{label}: código {resolved['code']}" + (f" = {resolved['commercial']}" if exact else (f" → {resolved['brand']} {resolved['family']}" if resolved['family'] else f" (marca {resolved['brand']})"))
                brand(resolved['brand'], r_src, priority, conf)
                dtype(resolved['category'], r_src, priority, conf, detail, specific=True)
                break

        announced_name = obs.name or getattr(obs, 'wps_device_name', '') or getattr(obs, 'ssid', '')
        if announced_name:
            if obs.name:
                source = 'Nombre autodeclarado' + (' en respuesta de escaneo BLE' if obs.name_source == 'scan_response' else '') + ': ' + obs.name
            elif getattr(obs, 'wps_device_name', ''):
                source = 'Nombre de dispositivo WPS/Red: ' + obs.wps_device_name
            else:
                source = 'SSID anunciado por AP: ' + obs.ssid
            result['evidence'].append(source)
            for rule in self.rules['names']:
                if re.search(rule['pattern'], announced_name, re.I):
                    brand(rule['brand'], source, 40, 'Baja')
                    if rule.get('category'): dtype(rule['category'], source, 40, 'Baja', specific=True)
                    break
            for rule in self.rules['categories']:
                if re.search(rule['pattern'], announced_name, re.I):
                    # Una palabra de tipo explícita ("Smart TV", "impresora"…) pesa más que la categoría implícita de la marca.
                    dtype(rule['category'], source, 41, 'Baja', specific=True)
                    break
            result['warnings'].append('Los nombres anunciados son modificables y no verifican autenticidad ni modelo comercial.')

        if obs.tech == 'wifi' and obs.role in ('ap', 'station'):
            result['network_role'] = 'Punto de acceso' if obs.role == 'ap' else 'Estación'; result['role_confidence'] = 'Alta'
            if obs.frame_type == 'red_local':
                evidence('network_role', f'Escaneo de la red local conectada: rol {result["network_role"]}.')
            else:
                evidence('network_role', f'Cabecera 802.11 ({obs.frame_type or "trama compatible"}): rol {result["network_role"]}.')

        if obs.cod is not None:
            decoded = classic_type(obs.cod)
            if decoded:
                dtype(decoded['category'], f'Clase Bluetooth autodeclarada 0x{obs.cod:06X}: {decoded["detail"]}', 80 if decoded['specific'] else 60, 'Alta', decoded['detail'], decoded['specific'])

        if obs.appearance is not None:
            decoded = self.appearance.get(str(obs.appearance))
            if decoded:
                dtype(decoded['category'], f'Appearance Bluetooth SIG 0x{obs.appearance:04X}: {decoded["name"]} (autodeclarado).', 90 if decoded['specific'] else 70, 'Alta', decoded['name'], decoded['specific'])

        decoded = wps_type(obs.wps_primary_device_type)
        if decoded:
            dtype(decoded['category'], 'Tipo primario WPS/Red autodeclarado: ' + decoded['detail'], 85 if decoded['specific'] else 65, 'Media', decoded['detail'], decoded['specific'])

        if resolved and resolved['commercial']:
            result['model'] = f"{resolved['commercial']} ({resolved['code']})" if resolved['code'].casefold() not in resolved['commercial'].casefold() else resolved['commercial']
            result['model_confidence'] = 'Alta' if obs.wps_model_name or obs.wps_model_number else 'Media'
            result['model_source'] = 'Código de modelo traducido a nombre comercial'
            evidence('model', 'Modelo: ' + result['model'])
        elif resolved and resolved['family']:
            result['model'] = f"{resolved['brand']} {resolved['family']} ({resolved['code']})"
            result['model_confidence'] = 'Media'
            result['model_source'] = 'Serie por prefijo del fabricante (modelo exacto no anunciado)'
            evidence('model', 'Serie confirmada por el prefijo del código: ' + result['model'])
        elif obs.wps_model_name or obs.wps_model_number:
            name = obs.wps_model_name; number = obs.wps_model_number
            result['model'] = name + ((' / ' + number) if number and number.casefold() not in name.casefold() else '') if name else number
            result['model_confidence'] = 'Media'; result['model_source'] = 'WPS (autodeclarado)'
            evidence('model', 'Modelo anunciado en WPS: ' + result['model'])

        for uuid in obs.services:
            normalized = uuid.upper().replace('-', '')
            short = normalized[4:8] if len(normalized) == 32 and normalized.startswith('0000') and normalized.endswith('00001000800000805F9B34FB') else normalized
            label = SERVICES.get(short)
            result['advertised_capabilities'].append(dict(uuid=uuid, name=label or 'Servicio sin interpretación local'))
            if short in PRINT_SERVICES:
                dtype('Impresora', f'Servicio Bluetooth de impresión ({short}: {label})', 75, 'Alta', label or 'Impresión', specific=True)
            elif short in PHONE_SERVICES:
                s_brand, s_cat, s_desc = PHONE_SERVICES[short]
                if s_brand: brand(s_brand, f'Servicio BLE {short} ({s_desc})', 44, 'Media')
                dtype(s_cat, f'Servicio BLE {short} ({s_desc})', 52, 'Media', s_desc, specific=True)

        if brands:
            chosen = max(brands, key=lambda x: x['priority'])
            result['brand'] = result['commercial_brand'] = chosen['value']
            result['brand_confidence'] = chosen['confidence']
            distinct = {x['value'] for x in brands}
            compatible = distinct.issubset({'Xiaomi', 'Redmi', 'POCO'}) or distinct.issubset({'Huawei', 'Honor'})
            if len(distinct) > 1 and not compatible:
                result['warnings'].append('Fuentes de marca contradictorias: ' + ', '.join(sorted(distinct)) + '. Se conserva la fuente explícita de mayor prioridad con confianza baja.')
                result['brand_confidence'] = 'Baja'
            elif distinct.issubset({'Xiaomi', 'Redmi', 'POCO'}):
                subbrand = next((x for x in brands if x['value'] in ('Redmi', 'POCO')), None)
                if subbrand:
                    result['brand'] = result['commercial_brand'] = subbrand['value']
                    result['brand_confidence'] = subbrand['confidence']

        if types:
            chosen = max(types, key=lambda x: x['priority'])
            if not chosen['specific']:
                refinement = next((x for x in types if x['specific'] and x['value'] != chosen['value'] and related(x['value'], chosen['value'])), None)
                if refinement: chosen = refinement
            result['category'] = result['device_type'] = chosen['value']
            result['category_confidence'] = chosen['confidence']
            result['category_detail'] = chosen['detail']
            if any(not related(x['value'], chosen['value']) for x in types):
                result['warnings'].append('Hay evidencias de tipo incompatibles; la categoría conserva la fuente de mayor prioridad, con confianza baja.')
                result['category_confidence'] = 'Baja'

        # Compute detected_brand across OUI, WPS, Name, BLE Company ID, or Radio Vendor
        company_brand = self.brand_for(result['company_identifier_owner']) if result['company_identifier_owner'] != 'Desconocido' else None
        if result['brand'] != 'Desconocido':
            result['detected_brand'] = result['brand']
        elif company_brand:
            result['detected_brand'] = company_brand
        elif result['company_identifier_owner'] != 'Desconocido':
            result['detected_brand'] = result['company_identifier_owner'].split(',')[0].split(' Inc')[0].split(' Co.')[0].strip()
        elif result['radio_vendor'] != 'No identificable':
            chip_short = result['radio_vendor'].split()[0].rstrip(',')
            result['detected_brand'] = chip_short

        # Compute 6-category target classification: Celular, Tablet, Laptop, Impresora, Router, Cañón
        cat = result['category']
        eff_brand = result['brand'] if result['brand'] != 'Desconocido' else company_brand
        if cat in CATEGORY_TO_TARGET:
            result['classification'] = CATEGORY_TO_TARGET[cat]
            result['classification_confidence'] = result['category_confidence'] if result['category_confidence'] != 'Desconocida' else 'Media'
            result['classification_source'] = f"Categoría identificada: {cat}" + (f" ({result['category_detail']})" if result['category_detail'] else '')
        elif cat != 'Desconocido':
            result['classification'] = 'Otro'
            result['classification_confidence'] = result['category_confidence']
            result['classification_source'] = f"Dispositivo {cat}"
        else:
            # Smart embedded classification by vendor, radio module, role, and technology
            if ble_hint and MERGE.get(ble_hint.get('target'), ble_hint.get('target')) in TARGET_CLASSES:
                result['classification'] = MERGE.get(ble_hint['target'], ble_hint['target'])
                result['classification_confidence'] = 'Media'
                result['classification_source'] = f"Protocolo BLE ({ble_hint['detail']})"
            elif eff_brand == 'HP':
                # Solo es impresora si hay señal real de impresora (Wi-Fi Direct de impresora o palabra de impresora
                # en el nombre). Un punto de acceso / repetidor con OUI de HP NO se clasifica como impresora.
                name_text = ' '.join(filter(None, [obs.ssid, getattr(obs, 'wps_device_name', ''), obs.name]))
                printer_signal = bool(re.search(r'DIRECT-.*HP|LaserJet|OfficeJet|DeskJet|Smart Tank|Ink Tank|PageWide|Neverstop|印表|printer|impresora', name_text, re.I))
                if obs.tech == 'ble' or (obs.tech == 'wifi' and obs.role == 'ap' and printer_signal):
                    result['classification'] = 'Impresora'
                    result['classification_confidence'] = 'Media'
                    result['classification_source'] = 'Equipo HP en modo Wi-Fi Direct / BLE (Impresora)'
                elif obs.tech == 'wifi' and obs.role == 'ap':
                    result['classification'] = 'Router'
                    result['classification_confidence'] = 'Baja'
                    result['classification_source'] = 'Punto de acceso con OUI HP (sin señal de impresora)'
                else:
                    result['classification'] = 'Laptop'
                    result['classification_confidence'] = 'Media'
                    result['classification_source'] = 'Estación Wi-Fi / BT HP (Laptop)'
            elif eff_brand == 'Epson':
                name_text = ' '.join(filter(None, [obs.ssid, getattr(obs, 'wps_device_name', ''), obs.name]))
                printer_signal = bool(re.search(r'DIRECT-.*(EPSON|Print)|EcoTank|WorkForce|EPSON', name_text, re.I))
                if obs.tech == 'wifi' and obs.role == 'ap' and printer_signal:
                    result['classification'] = 'Impresora'
                    result['classification_confidence'] = 'Media'
                    result['classification_source'] = 'Punto de acceso Epson Wi-Fi Direct (Impresora)'
                elif obs.tech == 'wifi' and obs.role == 'ap':
                    result['classification'] = 'Router'
                    result['classification_confidence'] = 'Baja'
                    result['classification_source'] = 'Punto de acceso con OUI Epson (sin señal de impresora)'
                else:
                    result['classification'] = 'Cañón'
                    result['classification_confidence'] = 'Media'
                    result['classification_source'] = 'Módulo inalámbrico Seiko Epson (Cañón / Proyector)'
            elif eff_brand and eff_brand in self.vendor_defaults.get('Cañón', []):
                result['classification'] = 'Cañón'
                result['classification_confidence'] = 'Media'
                result['classification_source'] = f"Fabricante de proyectores/cañones ({eff_brand})"
            elif eff_brand and eff_brand in self.vendor_defaults.get('Impresora', []):
                result['classification'] = 'Impresora'
                result['classification_confidence'] = 'Media'
                result['classification_source'] = f"Fabricante de equipos de impresión ({eff_brand})"
            elif eff_brand and (eff_brand in self.vendor_defaults.get('Router', []) or (obs.tech == 'wifi' and obs.role == 'ap' and eff_brand in ('ZTE', 'Huawei', 'Nokia', 'ASUS'))):
                result['classification'] = 'Router'
                result['classification_confidence'] = 'Media'
                result['classification_source'] = f"Fabricante de red / Punto de acceso ({eff_brand})"
            elif eff_brand and eff_brand in self.vendor_defaults.get('Tablet', []):
                result['classification'] = 'Tablet'
                result['classification_confidence'] = 'Media'
                result['classification_source'] = f"Fabricante de tablets ({eff_brand})"
            elif eff_brand and eff_brand in self.vendor_defaults.get('Laptop', []):
                result['classification'] = 'Laptop'
                result['classification_confidence'] = 'Media'
                result['classification_source'] = f"Fabricante de laptops/cómputo ({eff_brand})"
            elif result['radio_vendor'] != 'No identificable' and PC_RADIO_CHIPS.search(result['radio_vendor']) and obs.role != 'ap':
                result['classification'] = 'Laptop'
                result['classification_confidence'] = 'Media'
                result['classification_source'] = f"Tarjeta inalámbrica de PC/Laptop ({result['radio_vendor']})"
            elif result['radio_vendor'] != 'No identificable' and MOBILE_RADIO_CHIPS.search(result['radio_vendor']) and obs.role != 'ap':
                result['classification'] = 'Celular'
                result['classification_confidence'] = 'Baja'
                result['classification_source'] = f"Chipset móvil Wi-Fi/BT ({result['radio_vendor']})"
            elif eff_brand and eff_brand in self.vendor_defaults.get('Celular', []):
                result['classification'] = 'Celular'
                result['classification_confidence'] = 'Media'
                role_note = ' (Hotspot móvil)' if obs.tech == 'wifi' and obs.role == 'ap' else ''
                result['classification_source'] = f"Fabricante de dispositivos móviles ({eff_brand}){role_note}"
            elif obs.tech == 'wifi' and obs.role == 'ap':
                result['classification'] = 'Router'
                result['classification_confidence'] = 'Baja'
                result['classification_source'] = 'Punto de acceso Wi-Fi activo (AP)'
            elif obs.tech == 'wifi':
                # Station or management frame from client device (commonly Smartphones/Tablets with randomized MAC)
                result['classification'] = 'Celular'
                result['classification_confidence'] = 'Baja'
                result['classification_source'] = 'Cliente móvil Wi-Fi activo (MAC aleatoria / estación)'
            elif obs.tech == 'ble':
                if getattr(obs, 'tx_power', None) is not None and obs.tx_power >= 8:
                    result['classification'] = 'Laptop'
                    result['classification_confidence'] = 'Baja'
                    result['classification_source'] = f'Anuncio BLE de alta potencia ({obs.tx_power} dBm)'
                elif getattr(obs, 'adv_type', None) == 2:
                    result['classification'] = 'Tablet'
                    result['classification_confidence'] = 'Baja'
                    result['classification_source'] = 'Anuncio BLE escaneable móvil'
                else:
                    result['classification'] = 'Celular'
                    result['classification_confidence'] = 'Baja'
                    result['classification_source'] = 'Anuncio BLE de dispositivo móvil'
            elif obs.tech == 'classic':
                result['classification'] = 'Celular'
                result['classification_confidence'] = 'Baja'
                result['classification_source'] = 'Dispositivo Bluetooth Classic descubrible'

        # Conservar el subtipo granular (Celular/Tablet) para las etiquetas y plegar la clase objetivo.
        result['classification_subtype'] = result['classification']
        result['classification'] = MERGE.get(result['classification'], result['classification'])
        result['target_class'] = result['classification']
        result['is_target_class'] = result['classification'] in TARGET_CLASSES

        # Promote classification & detected_brand into primary category/device_type/brand so UI table and filters show them directly
        if result['category'] == 'Desconocido' and result['classification'] in TARGET_CLASSES:
            result['category'] = result['device_type'] = result['classification_subtype']
            result['category_confidence'] = result['classification_confidence']
            result['category_detail'] = result['classification_source']
            evidence('category', result['classification_source'])

        if result['brand'] == 'Desconocido' and result['detected_brand'] != 'Desconocido':
            result['brand'] = result['commercial_brand'] = result['detected_brand']
            result['brand_confidence'] = 'Baja' if result['classification_confidence'] == 'Baja' else 'Media'

        # Compute human-friendly detected_device label and populate model if not set
        b_label = result['brand'] if result['brand'] != 'Desconocido' else ''
        if result['model'] != 'No identificable':
            m_label = result['model']
            result['detected_device'] = f"{b_label} {m_label}".strip() if b_label and b_label.casefold() not in m_label.casefold() else m_label
        elif announced_name:
            clean_name = re.sub(r'\s*\(\d{1,3}(?:\.\d{1,3}){3}\)$', '', announced_name.strip())
            result['detected_device'] = f"{b_label} {clean_name}".strip() if b_label and b_label.casefold() not in clean_name.casefold() else clean_name
            result['model'] = result['detected_device']
            result['model_source'] = 'Nombre / SSID / Red'
            result['model_confidence'] = 'Baja'
        elif ble_hint and ble_hint.get('device'):
            result['detected_device'] = ble_hint['device']
            result['model'] = ble_hint['device']
            result['model_source'] = 'Protocolo BLE'
            result['model_confidence'] = 'Media'
        elif result['classification'] in TARGET_CLASSES:
            disp = result.get('classification_subtype') or result['classification']
            if disp == 'Celular y Tablet': disp = 'Celular'
            if b_label == 'Apple' and disp == 'Celular':
                result['detected_device'] = 'Apple iPhone (probable)'
            elif b_label:
                role_tag = ' (Hotspot)' if disp == 'Celular' and obs.tech == 'wifi' and obs.role == 'ap' else ''
                result['detected_device'] = f"{disp} {b_label}{role_tag}"
            else:
                result['detected_device'] = f"{disp} ({obs.tech.upper()})"
            result['model'] = result['detected_device']
            result['model_source'] = result['classification_source']
            result['model_confidence'] = result['classification_confidence']
        elif result['category'] != 'Desconocido':
            result['detected_device'] = f"{result['category']} {b_label}".strip() if b_label else f"{result['category']} ({obs.tech.upper()})"
            result['model'] = result['detected_device']
            result['model_source'] = 'Clase anunciada'
            result['model_confidence'] = result['category_confidence']

        grades = [result[k] for k in ('brand_confidence', 'category_confidence') if result[k] != 'Desconocida']
        if grades: result['confidence'] = min(grades, key=lambda x: RANK[x])

        # Plain-language summary for non-technical readers.
        if resolved and resolved['commercial']:
            how = f"El equipo anunció su código de modelo ({resolved['code']})"
        elif resolved and resolved['family']:
            how = f"El prefijo del código ({resolved['code']}) confirma la marca y la serie"
        elif obs.wps_model_name or obs.wps_model_number:
            how = 'El equipo anunció su modelo'
        elif obs.frame_type == 'red_local' and announced_name:
            how = 'Nombre del equipo en la red Wi-Fi conectada'
        elif obs.name and obs.tech == 'classic':
            how = 'Nombre Bluetooth visible del equipo'
        elif obs.name:
            how = 'Nombre anunciado por Bluetooth'
        elif getattr(obs, 'wps_device_name', ''):
            how = 'Nombre anunciado por Wi-Fi'
        elif obs.ssid:
            how = 'Nombre de la red Wi-Fi que emite'
        elif ble_hint:
            how = 'Señal Bluetooth propia del fabricante'
        elif any((VENDOR_IES.get(t) or VENDOR_IES.get(t[:6]) or (None,))[0] for t in vendor_ies):
            how = 'Firma del fabricante en su señal Wi-Fi'
        elif oui:
            how = 'Fabricante de su tarjeta de red (MAC)'
        elif result['classification'] in TARGET_CLASSES:
            how = 'Estimado solo por el tipo de señal'
        else:
            how = 'Sin datos suficientes'
        result['how_identified'] = how
        level = result['model_confidence'] if result['model_source'] not in ('No disponible',) and result['model_confidence'] != 'Desconocida' else result['confidence']
        if how.startswith('Nombre') and result['brand_confidence'] != 'Desconocida' and result['classification'] in TARGET_CLASSES:
            level = 'Media'  # el nombre coincide con un modelo conocido de la marca
        if level == 'Desconocida' or how.startswith('Estimado') or how.startswith('Sin datos'): level = 'Baja'
        result['certainty'] = level

        result['identification_evidence'] = list(dict.fromkeys(result['evidence']))
        result['evidence'] = result['identification_evidence']
        if self.last_error: result['warnings'].append(self.last_error)
        return result
