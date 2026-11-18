"""Active local network (LAN/Wi-Fi) discovery to extract exact brand, model, and device type
(Celular, Tablet, Laptop, Impresora, Router, Cañón) via ARP, SSDP/UPnP, mDNS (unicast), NetBIOS, PJLink, and IPP/JetDirect,
complementing ESP32 promiscuous RF scanning of external networks."""
import concurrent.futures, ipaddress, os, platform, re, socket, struct, subprocess, urllib.request, xml.etree.ElementTree as ET
from .models import Observation

MAC_RE = re.compile(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}')
IPV4_RE = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

def normalize_mac(raw: str) -> str | None:
    m = raw.strip().replace('-', ':').upper()
    if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', m):
        return None
    if m in ('00:00:00:00:00:00', 'FF:FF:FF:FF:FF:FF') or (int(m[:2], 16) & 1):
        return None
    return m

def local_ipv4_and_gateway():
    """Return (local_ip, gateway_ip) without external internet traffic."""
    local_ip = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
    except OSError:
        pass
    gateway = None
    try:
        if os.name == 'nt':
            out = subprocess.run(['route', 'print', '0.0.0.0'], capture_output=True, text=True, timeout=3).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
                    gateway = parts[2]; break
        else:
            out = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True, timeout=3).stdout
            m = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', out)
            if m: gateway = m.group(1)
    except Exception:
        pass
    if not gateway and local_ip:
        prefix = '.'.join(local_ip.split('.')[:3])
        gateway = prefix + '.1'
    return local_ip, gateway

def trigger_subnet_arp(local_ip: str):
    """Send fast non-blocking UDP packets across the /24 subnet so the OS populates its ARP table."""
    try:
        net = ipaddress.ip_network(local_ip + '/24', strict=False)
    except ValueError:
        return
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setblocking(False)
            for host in net.hosts():
                ip = str(host)
                if ip == local_ip: continue
                try: s.sendto(b'\x00', (ip, 5353))
                except OSError: pass
    except OSError:
        pass

def read_arp_table() -> dict[str, str]:
    """Return {ip: mac} from the operating system ARP table."""
    entries = {}
    try:
        out = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=4).stdout
        for line in out.splitlines():
            ip_m = IPV4_RE.search(line)
            mac_m = MAC_RE.search(line)
            if ip_m and mac_m:
                ip = ip_m.group(0)
                if ip.startswith(('224.', '239.', '255.')) or ip.endswith('.255'):
                    continue
                mac = normalize_mac(mac_m.group(0))
                if mac:
                    entries[ip] = mac
    except Exception:
        pass
    return entries

def ssdp_discover(timeout: float = 1.2) -> dict[str, dict]:
    """Query UPnP/SSDP devices on the local LAN and fetch their XML model/brand descriptions."""
    results = {}
    msg = (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 1\r\n'
        'ST: ssdp:all\r\n\r\n'
    ).encode('ascii')
    locations = {}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.settimeout(timeout)
            s.sendto(msg, ('239.255.255.250', 1900))
            while True:
                try:
                    data, addr = s.recvfrom(4096)
                except OSError:
                    break
                ip = addr[0]
                text = data.decode('utf-8', errors='ignore')
                loc = re.search(r'(?i)^LOCATION:\s*(http://[^\r\n]+)', text, re.M)
                srv = re.search(r'(?i)^SERVER:\s*([^\r\n]+)', text, re.M)
                if srv and ip not in results:
                    results[ip] = {'server': srv.group(1).strip()}
                if loc and ip not in locations:
                    locations[ip] = loc.group(1).strip()
    except OSError:
        pass

    def fetch_xml(ip_loc):
        ip, url = ip_loc
        info = results.get(ip, {})
        try:
            with urllib.request.urlopen(url, timeout=1.2) as r:
                xml_bytes = r.read(65536)
            root = ET.fromstring(xml_bytes)
            for elem in root.iter():
                tag = elem.tag.split('}')[-1]
                val = (elem.text or '').strip()
                if not val: continue
                if tag == 'manufacturer' and 'manufacturer' not in info:
                    info['manufacturer'] = val[:64]
                elif tag == 'modelName' and 'model_name' not in info:
                    info['model_name'] = val[:32]
                elif tag == 'modelNumber' and 'model_number' not in info:
                    info['model_number'] = val[:32]
                elif tag == 'friendlyName' and 'friendly_name' not in info:
                    info['friendly_name'] = val[:64]
                elif tag == 'deviceType' and 'device_type' not in info:
                    info['device_type'] = val
        except Exception:
            pass
        return ip, info

    if locations:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            for ip, info in ex.map(fetch_xml, locations.items()):
                results[ip] = info
    return results

def netbios_name(ip: str, timeout: float = 0.35) -> str:
    """Query NetBIOS Node Status (UDP 137) to get Windows/Printer/Samba hostname."""
    query = (
        b'\x82\x28\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
        b'\x20CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00'
        b'\x00\x21\x00\x01'
    )
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(query, (ip, 137))
            data, _ = s.recvfrom(1024)
        if len(data) > 57:
            num_names = data[56]
            offset = 57
            for _ in range(num_names):
                if offset + 18 > len(data): break
                raw_name = data[offset:offset+15].decode('ascii', errors='ignore').strip()
                suffix = data[offset+15]
                flags = struct.unpack('>H', data[offset+16:offset+18])[0]
                offset += 18
                if suffix in (0x00, 0x20) and not (flags & 0x8000) and raw_name:
                    return raw_name
    except OSError:
        pass
    return ''

def _dns_name(data: bytes, offset: int, depth: int = 0) -> tuple[str, int]:
    labels = []; jumped = False; end = offset
    while offset < len(data) and depth < 16:
        n = data[offset]
        if n == 0:
            offset += 1; break
        if n & 0xC0 == 0xC0:
            if offset + 1 >= len(data): break
            ptr = ((n & 0x3F) << 8) | data[offset + 1]
            if not jumped: end = offset + 2
            jumped = True; offset = ptr; depth += 1; continue
        labels.append(data[offset + 1:offset + 1 + n].decode('utf-8', errors='replace')); offset += 1 + n
    return '.'.join(labels), (end if jumped else offset)

def _dns_question(name: str, qtype: int) -> bytes:
    out = b''.join(bytes([len(p)]) + p.encode('utf-8') for p in name.split('.') if p) + b'\x00'
    return out + struct.pack('>HH', qtype, 0x8001)  # QU bit: unicast response requested

def mdns_identity(ip: str, timeout: float = 0.6) -> dict:
    """Unicast mDNS (UDP 5353) to one host: reverse hostname (iPhone/iPad/Mac/Windows) and model TXT keys if published."""
    rev = '.'.join(reversed(ip.split('.'))) + '.in-addr.arpa'
    questions = [(rev, 12), ('_device-info._tcp.local', 12), ('_companion-link._tcp.local', 12)]
    packet = struct.pack('>HHHHHH', 0x4D44, 0, len(questions), 0, 0, 0) + b''.join(_dns_question(n, t) for n, t in questions)
    info = {}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout); s.sendto(packet, (ip, 5353))
            data, _ = s.recvfrom(9000)
    except OSError:
        return info
    try:
        qd, an, ns, ar = struct.unpack('>HHHH', data[4:12]); offset = 12
        for _ in range(qd):
            _, offset = _dns_name(data, offset); offset += 4
        for _ in range(an + ns + ar):
            name, offset = _dns_name(data, offset)
            rtype, _, _, rdlen = struct.unpack('>HHIH', data[offset:offset + 10]); offset += 10
            rdata_at = offset; offset += rdlen
            if rtype == 12 and name.endswith('in-addr.arpa'):
                host, _ = _dns_name(data, rdata_at)
                if host: info.setdefault('hostname', host.split('.')[0])
            elif rtype == 1 and name.endswith('.local') and 'hostname' not in info:
                info['hostname'] = name.split('.')[0]
            elif rtype == 16:
                at = rdata_at
                while at < rdata_at + rdlen:
                    n = data[at]; entry = data[at + 1:at + 1 + n].decode('utf-8', errors='ignore'); at += 1 + n
                    key, _, value = entry.partition('=')
                    if key.lower() in ('model', 'rpmd', 'md') and value and 'model' not in info:
                        info['model'] = value[:32]
    except (struct.error, IndexError):
        pass
    return info

def probe_port(ip: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False

def query_pjlink(ip: str, timeout: float = 0.4) -> tuple[str, str]:
    """Query projector PJLink protocol (TCP 4352) for exact projector brand (INF1) and model (INF2)."""
    mfg, mdl = '', ''
    try:
        with socket.create_connection((ip, 4352), timeout=timeout) as s:
            s.settimeout(timeout)
            with contextlib_suppress():
                _ = s.recv(64)
            s.sendall(b'%1INF1 ?\r')
            r1 = s.recv(128).decode('ascii', errors='ignore')
            if '=OK' in r1:
                mfg = r1.split('=', 1)[1].replace('OK', '').strip()[:64]
            s.sendall(b'%1INF2 ?\r')
            r2 = s.recv(128).decode('ascii', errors='ignore')
            if '=OK' in r2:
                mdl = r2.split('=', 1)[1].replace('OK', '').strip()[:32]
    except OSError:
        pass
    return mfg, mdl

class contextlib_suppress:
    def __enter__(self): return self
    def __exit__(self, *args): return True

def http_title(ip: str, port: int = 80, timeout: float = 0.45) -> str:
    """Read HTTP Server header or HTML <title> from local web interface (routers, printers, projectors)."""
    try:
        req = urllib.request.Request(f'http://{ip}:{port}/', headers={'User-Agent': 'ESP32-Observatorio/2.2'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            srv = r.headers.get('Server', '')
            body = r.read(16384).decode('utf-8', errors='ignore')
        m = re.search(r'<title[^>]*>([^<]{2,80})</title>', body, re.I)
        if m:
            title = re.sub(r'\s+', ' ', m.group(1)).strip()
            if title and not any(x in title.lower() for x in ('redirect', '404', 'error', 'index of')):
                return title[:64]
        return srv[:64]
    except Exception:
        return ''

def inspect_host(ip: str, mac: str, gateway: str | None, ssdp_info: dict) -> Observation:
    """Build an enriched Wi-Fi Observation from active local network probing of (ip, mac)."""
    is_gw = (ip == gateway)
    wps_mfg = ssdp_info.get('manufacturer', '')
    wps_model = ssdp_info.get('model_name', '')
    wps_num = ssdp_info.get('model_number', '')
    friendly = ssdp_info.get('friendly_name', '')
    upnp_type = ssdp_info.get('device_type', '')
    wps_pdt = ''

    # Fast port signature check
    is_projector = probe_port(ip, 4352) or probe_port(ip, 3629)
    is_printer = False if is_projector else (probe_port(ip, 9100) or probe_port(ip, 631) or probe_port(ip, 515))
    is_ios = False if (is_projector or is_printer or is_gw) else probe_port(ip, 62078)
    is_smb = False if (is_projector or is_printer or is_gw or is_ios) else (probe_port(ip, 445) or probe_port(ip, 139) or probe_port(ip, 3389))

    if is_projector:
        wps_pdt = '00070050F2040003'  # Cañón / Projector
        pj_mfg, pj_mdl = query_pjlink(ip)
        if pj_mfg and not wps_mfg: wps_mfg = pj_mfg
        if pj_mdl and not wps_model: wps_model = pj_mdl
    elif is_printer or 'Printer' in upnp_type or 'Scanner' in upnp_type:
        wps_pdt = '00030050F2040001'  # Impresora
    elif is_gw or 'InternetGatewayDevice' in upnp_type or 'WANDevice' in upnp_type or 'WFADevice' in upnp_type:
        wps_pdt = '00060050F2040002'  # Router
    elif is_ios:
        wps_pdt = '000A0050F2040001'  # Celular (iPhone / iOS)
        if not wps_mfg: wps_mfg = 'Apple'
    elif is_smb:
        wps_pdt = '00010050F2040003'  # Laptop / PC

    nb = netbios_name(ip)
    mdns = {} if (is_gw or is_printer or is_projector) else mdns_identity(ip)
    mdns_host = mdns.get('hostname', '')
    if mdns.get('model') and not wps_model: wps_model = mdns['model']
    if mdns_host and re.search(r'iPhone|iPad', mdns_host + wps_model, re.I) and not wps_mfg: wps_mfg = 'Apple'
    if mdns_host and re.search(r'MacBook|iMac|Mac-?mini', mdns_host + wps_model, re.I) and not wps_mfg: wps_mfg = 'Apple'
    if re.search(r'iPad', mdns_host + wps_model, re.I): wps_pdt = '00010050F2040005'  # Tablet (puerto 62078 también abre en iPad)
    elif re.search(r'MacBook', mdns_host + wps_model, re.I): wps_pdt = '00010050F2040003'
    elif not wps_pdt and re.search(r'iPhone', mdns_host + wps_model, re.I): wps_pdt = '000A0050F2040001'
    rdns = ''
    if not nb and not friendly and not mdns_host:
        try:
            socket.setdefaulttimeout(0.35)
            rdns = socket.gethostbyaddr(ip)[0].split('.')[0]
        except OSError:
            pass
    title = ''
    if is_gw or is_printer or is_projector:
        title = http_title(ip, 80)

    best_name = friendly or mdns_host or nb or title or rdns
    if best_name and f'({ip})' not in best_name:
        best_name = f'{best_name} ({ip})'
    elif not best_name:
        best_name = f'Red local ({ip})'

    return Observation(
        event='observation',
        v=2,
        tech='wifi',
        mac=mac,
        name=best_name[:248],
        name_complete=bool(friendly or mdns_host or nb or title or rdns),
        name_source='wps' if (friendly or title) else 'advertisement',
        wps_manufacturer=wps_mfg[:64],
        wps_model_name=(wps_model or title)[:32],
        wps_model_number=wps_num[:32],
        wps_device_name=(friendly or mdns_host or nb or rdns)[:64],
        wps_primary_device_type=wps_pdt,
        role='ap' if is_gw else 'station',
        frame_type='red_local',
    )

def scan_connected_network() -> list[Observation]:
    """Discover all devices on the currently connected Wi-Fi/LAN network and return enriched Observations."""
    local_ip, gateway = local_ipv4_and_gateway()
    if not local_ip:
        return []
    trigger_subnet_arp(local_ip)
    ssdp = ssdp_discover(timeout=1.0)
    arp = read_arp_table()
    if not arp:
        return []
    observations = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        futures = [
            ex.submit(inspect_host, ip, mac, gateway, ssdp.get(ip, {}))
            for ip, mac in arp.items()
        ]
        for f in concurrent.futures.as_completed(futures):
            try:
                observations.append(f.result())
            except Exception:
                pass
    return observations
