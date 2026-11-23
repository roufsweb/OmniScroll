"""
protocol.py — OmniScroll Multi-Transport Protocol (OMP)
Handles dual-transport USB CDC Serial and Wi-Fi UDP streaming,
auto-discovery, device verification, and packet serialization.
"""
import socket
import select
import struct
import time
import logging
import serial
import serial.tools.list_ports

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEVICE_PRODUCT_ID = "OMNISCROLL-V2"
ESP32_S2_USB_VID = 0x303A
ESP32_S2_USB_PID = 0x4F5B

# Ports
UDP_DISCOVERY_PORT = 4210
UDP_STREAM_PORT    = 4211

# Magic bytes
DISCOVERY_MAGIC_RWP  = b'ROUFS'
DISCOVERY_MAGIC_OMNI = b'OMNI'
RWP_MAGIC            = 0x5257  # 'R', 'W' in ASCII (RoufsWeb Protocol)
OMP_LEGACY_MAGIC     = 0xAA55  # Legacy fallback magic
OMP_MAGIC            = RWP_MAGIC

# Packet Types
PKT_MOTION  = 0x01  # Optical wheel delta
PKT_ACTION  = 0x02  # Touch / Modifier action
PKT_GESTURE = 0x03  # Flick gesture
PKT_STATUS  = 0x04  # Mode change / status


class OMPPacket:
    """
    Binary 9-byte packet structure (RoufsWeb Protocol RWP / OMP):
    Offset Type    Field       Description
    0-1    uint16  magic       0x5257 ('RW') or 0xAA55 (legacy)
    2      uint8   type        0x01 Motion, 0x02 Action, 0x03 Gesture, 0x04 Status
    3      uint8   seq         Sequence number (0-255)
    4      int8    delta       Motion delta (-128 to 127)
    5      uint8   mode        Current mode index (0-7)
    6      uint8   action      Action code (0-25, 99)
    7      uint8   flags       bit 0: high-res, bit 1: touch active, bit 2: usb mounted
    8      uint8   checksum    XOR sum of bytes 0-7
    """
    __slots__ = ('magic', 'type', 'seq', 'delta', 'mode', 'action', 'flags', 'checksum')

    def __init__(self, pkt_type=0, seq=0, delta=0, mode=0, action=0, flags=0, magic=RWP_MAGIC):
        self.magic = magic
        self.type = pkt_type
        self.seq = seq
        self.delta = delta
        self.mode = mode
        self.action = action
        self.flags = flags
        self.checksum = 0

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) < 9:
            return None
        magic, ptype, seq, delta, mode, action, flags, chk = struct.unpack("<HBBbBBBB", data[:9])
        if magic != RWP_MAGIC and magic != OMP_LEGACY_MAGIC:
            return None
        # Verify XOR checksum
        computed = 0
        for b in data[:8]:
            computed ^= b
        if computed != chk:
            return None
        pkt = cls(ptype, seq, delta, mode, action, flags, magic=magic)
        pkt.checksum = chk
        return pkt


    @property
    def is_high_res(self) -> bool:
        return bool(self.flags & 0x01)

    @property
    def is_touched(self) -> bool:
        return bool(self.flags & 0x02)

    @property
    def is_usb_mounted(self) -> bool:
        return bool(self.flags & 0x04)


# Alias for backward compatibility
RWPPacket = OMPPacket


class SerialStreamManager:
    """Manages physical USB CDC serial communication with OmniScroll."""
    def __init__(self):
        self.serial_conn = None
        self.active_port = None

    @staticmethod
    def list_ports():
        """Scans system for COM ports matching Espressif VID 0x303A, strictly filtering Bluetooth."""
        ports = serial.tools.list_ports.comports()
        detected = []
        for p in ports:
            hwid_upper = str(p.hwid).upper()
            desc_upper = str(p.description).upper()
            # Strict Peripheral Safety: NEVER touch or probe Bluetooth ports
            if "BTHENUM" in hwid_upper or "BLUETOOTH" in desc_upper or "BTH" in hwid_upper:
                continue

            is_match = (p.vid == ESP32_S2_USB_VID)
            if not is_match:
                is_match = f"VID:{ESP32_S2_USB_VID:04X}" in hwid_upper or "303A" in hwid_upper
            if is_match:
                detected.append({
                    "port": p.device,
                    "desc": p.description,
                    "hwid": p.hwid,
                    "dev_type": "ESP32-S2"
                })
        return detected

    @staticmethod
    def probe_port(port_name, baudrate=115200) -> bool:
        """Sends 0xFE probe byte with DTR/RTS asserted and checks for genuine OmniScroll response."""
        try:
            s = serial.Serial()
            s.port = port_name
            s.baudrate = baudrate
            s.timeout = 0.5
            s.write_timeout = 0.2
            s.dtr = True
            s.rts = True
            s.open()
            s.reset_input_buffer()
            s.reset_output_buffer()
            s.write(b'\xFE')
            s.flush()
            time.sleep(0.12)
            resp = b""
            if s.in_waiting > 0:
                resp = s.read(s.in_waiting)
            s.close()
            return DEVICE_PRODUCT_ID.encode() in resp or b"OMNISCROLL" in resp
        except Exception as e:
            logging.debug(f"probe_port {port_name} error: {e}")
            return False

    def connect(self, port_name, baudrate=115200, bypass_check=False) -> bool:
        self.disconnect()
        try:
            self.serial_conn = serial.Serial()
            self.serial_conn.port = port_name
            self.serial_conn.baudrate = baudrate
            self.serial_conn.timeout = 0.1
            self.serial_conn.write_timeout = 0.2
            self.serial_conn.dtr = True
            self.serial_conn.rts = True
            self.serial_conn.open()
            self.serial_conn.reset_input_buffer()

            if not bypass_check:
                self.serial_conn.write(b'\xFE')
                self.serial_conn.flush()
                time.sleep(0.12)
                resp = b""
                if self.serial_conn.in_waiting > 0:
                    resp = self.serial_conn.read(self.serial_conn.in_waiting)
                if DEVICE_PRODUCT_ID.encode() not in resp and b"OMNISCROLL" not in resp:
                    logging.warning(f"Device on {port_name} is not OmniScroll. Rejecting.")
                    self.serial_conn.close()
                    self.serial_conn = None
                    return False

            self.active_port = port_name
            logging.info(f"OmniScroll verified and connected on {port_name}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to COM port {port_name}: {e}")
            self.serial_conn = None
            self.active_port = None
            return False

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.serial_conn = None
        self.active_port = None

    def is_connected(self) -> bool:
        return self.serial_conn is not None and self.serial_conn.is_open

    def send_command(self, cmd: str) -> bool:
        if not self.is_connected():
            return False
        try:
            line = (cmd + "\n").encode('utf-8')
            self.serial_conn.write(line)
            self.serial_conn.flush()
            return True
        except Exception as e:
            logging.error(f"Serial send_command error: {e}")
            self.disconnect()
            return False

    def read_lines(self) -> list:
        if not self.is_connected():
            return []
        lines = []
        try:
            while self.serial_conn.in_waiting > 0:
                raw = self.serial_conn.readline()
                if raw:
                    line = raw.decode('utf-8', errors='ignore').strip()
                    if line:
                        lines.append(line)
        except Exception as e:
            logging.info(f"Serial connection broken: {e}")
            self.disconnect()
            return []
        return lines


class WiFiStreamManager:
    """Manages Wi-Fi UDP beacon discovery and real-time OMP packet streaming."""
    def __init__(self):
        self.stream_sock = None
        self.target_ip = None
        self.target_port = UDP_STREAM_PORT
        self.last_rx_time = 0
        self.last_beacon_info = {}
        self.last_known_ip = None

    @staticmethod
    def get_broadcast_targets(last_ip=None) -> list:
        targets = set()
        targets.add('255.255.255.255')
        try:
            # Query local outbound interface to determine primary active LAN subnet
            s_tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s_tmp.connect(('8.8.8.8', 80))
            local_ip = s_tmp.getsockname()[0]
            s_tmp.close()
            parts = local_ip.split('.')
            if len(parts) == 4:
                targets.add(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
        except Exception:
            pass
        try:
            host = socket.gethostname()
            for ip in socket.gethostbyname_ex(host)[2]:
                if not ip.startswith('127.'):
                    parts = ip.split('.')
                    if len(parts) == 4:
                        targets.add(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
        except Exception:
            pass
        if last_ip and last_ip != '0.0.0.0':
            targets.add(last_ip)
        return list(targets)

    def quick_probe_unicast(self, ip: str, timeout=0.15) -> bool:
        """Ultra-fast unicast direct probe to known device IP. Responds in <2ms if online."""
        if not ip or ip in ('0.0.0.0', '127.0.0.1'):
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(timeout)
            s.sendto(DISCOVERY_MAGIC_RWP, (ip, UDP_DISCOVERY_PORT))
            data, addr = s.recvfrom(512)
            s.close()
            text = data.decode(errors='ignore').strip()
            if text.startswith("ROUFSWEB:") or text.startswith("OMNISCROLL:"):
                self._parse_beacon(text, addr[0])
                self.last_known_ip = addr[0]
                return True
        except Exception:
            pass
        return False

    def micro_subnet_sweep(self, timeout=0.25) -> str:
        """Tier 4: Non-blocking parallel /24 subnet sweep for routers that filter broadcast and mDNS."""
        try:
            s_tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s_tmp.connect(('8.8.8.8', 80))
            local_ip = s_tmp.getsockname()[0]
            s_tmp.close()
            parts = local_ip.split('.')
            if len(parts) != 4:
                return None
            base = f"{parts[0]}.{parts[1]}.{parts[2]}"
            targets = [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" != local_ip]

            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setblocking(False)

            for t in targets:
                try:
                    s.sendto(DISCOVERY_MAGIC_RWP, (t, UDP_DISCOVERY_PORT))
                except Exception:
                    pass

            start_t = time.time()
            while time.time() - start_t < timeout:
                r, _, _ = select.select([s], [], [], 0.02)
                if r:
                    data, addr = s.recvfrom(512)
                    text = data.decode(errors='ignore').strip()
                    if "ROUFSWEB" in text or "OMNISCROLL" in text:
                        s.close()
                        self._parse_beacon(text, addr[0])
                        self.last_known_ip = addr[0]
                        logging.info(f"Micro-subnet sweep discovered OmniScroll at {addr[0]}")
                        return addr[0]
            s.close()
        except Exception as e:
            logging.debug(f"Micro-subnet sweep error: {e}")
        return None

    def discover(self, timeout=1.2, target_ip=None) -> str:
        """4-Tier Discovery Engine: Unicast Cache -> ZeroConf mDNS -> Multi-Broadcast -> Micro-Subnet Sweep."""
        # 1. Tier 1: Fast direct unicast check if device IP is already known
        check_ip = target_ip or self.last_known_ip
        if check_ip and self.quick_probe_unicast(check_ip, timeout=0.15):
            logging.info(f"Instant unicast discovery hit at {check_ip}")
            return check_ip

        # 2. Tier 2: ZeroConf mDNS hostname resolution (omniscroll.local)
        try:
            mdns_ip = socket.gethostbyname("omniscroll.local")
            if mdns_ip and self.quick_probe_unicast(mdns_ip, timeout=0.2):
                logging.info(f"mDNS ZeroConf discovery hit: omniscroll.local -> {mdns_ip}")
                self.last_known_ip = mdns_ip
                return mdns_ip
        except Exception:
            pass

        # 3. Tier 3: Multi-broadcast across global and directed subnet broadcasts
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind(('', UDP_DISCOVERY_PORT))
            s.settimeout(0.15)

            targets = self.get_broadcast_targets(check_ip)

            # Send burst of RWP and legacy probes
            for t in targets:
                try:
                    s.sendto(DISCOVERY_MAGIC_RWP, (t, UDP_DISCOVERY_PORT))
                    s.sendto(DISCOVERY_MAGIC_OMNI, (t, UDP_DISCOVERY_PORT))
                except Exception as e:
                    logging.debug(f"Active probe to {t} error: {e}")
            time.sleep(0.04)
            for t in targets:
                try:
                    s.sendto(DISCOVERY_MAGIC_RWP, (t, UDP_DISCOVERY_PORT))
                except Exception:
                    pass

            start_t = time.time()
            last_probe_t = start_t
            while time.time() - start_t < timeout:
                try:
                    data, addr = s.recvfrom(1024)
                    text = data.decode(errors='ignore').strip()
                    if text.startswith("ROUFSWEB:") or text.startswith("OMNISCROLL:"):
                        s.close()
                        logging.info(f"WiFi beacon discovered: {text} from {addr[0]}")
                        self._parse_beacon(text, addr[0])
                        self.last_known_ip = addr[0]
                        return addr[0]
                except socket.timeout:
                    pass

                # Retry active probe every 300ms
                if time.time() - last_probe_t >= 0.3:
                    last_probe_t = time.time()
                    for t in targets:
                        try:
                            s.sendto(DISCOVERY_MAGIC_RWP, (t, UDP_DISCOVERY_PORT))
                        except Exception:
                            pass
            s.close()
        except Exception as e:
            logging.debug(f"WiFi discovery error: {e}")

        # 4. Tier 4: Parallel Micro-Subnet Sweep (fallback if router drops all broadcasts/multicasts)
        return self.micro_subnet_sweep(timeout=0.25)

    def _parse_beacon(self, text: str, ip: str):
        # Format: ROUFSWEB:OMNISCROLL:<IP>:PORT=4211:VER=2.1:MODE=<Mode>:USB=<0|1>:BRAND=roufsweb
        # Or legacy: OMNISCROLL:<IP>:PORT=4211:VER=2.0:MODE=<Mode>:USB=<0|1>
        parts = text.split(":")
        info = {"ip": ip, "brand": "roufsweb"}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                info[k.lower()] = v
        self.last_beacon_info = info

    def connect(self, ip: str) -> bool:
        self.disconnect()
        try:
            self.stream_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.stream_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.stream_sock.bind(('', UDP_STREAM_PORT))
            self.stream_sock.setblocking(False)
            self.target_ip = ip
            self.last_rx_time = time.time()

            # Send connection greeting / probe
            self.stream_sock.sendto(b"GET:STATUS\n", (self.target_ip, UDP_STREAM_PORT))
            logging.info(f"WiFi UDP stream bound to {ip}:{UDP_STREAM_PORT}")
            return True
        except Exception as e:
            logging.error(f"Failed to bind WiFi stream socket: {e}")
            self.stream_sock = None
            return False

    def disconnect(self):
        if self.stream_sock:
            try:
                self.stream_sock.close()
            except:
                pass
        self.stream_sock = None
        self.target_ip = None

    def is_connected(self) -> bool:
        # 3.5-second window: accommodates 2 missed ping intervals before fast, snappy disconnect
        return self.stream_sock is not None and (time.time() - self.last_rx_time < 3.5)

    def send_ping(self) -> bool:
        return self.send_command("PING")

    def send_command(self, cmd: str) -> bool:
        if not self.stream_sock or not self.target_ip:
            return False
        try:
            payload = (cmd + "\n").encode('utf-8')
            self.stream_sock.sendto(payload, (self.target_ip, UDP_STREAM_PORT))
            return True
        except Exception as e:
            logging.error(f"WiFi UDP send_command error: {e}")
            return False

    def receive_packets(self) -> tuple:
        """
        Reads any available UDP datagrams non-blockingly.
        Returns (list_of_OMPPacket, list_of_ascii_lines)
        """
        if not self.stream_sock:
            return ([], [])

        omp_packets = []
        ascii_lines = []

        try:
            while True:
                r, _, _ = select.select([self.stream_sock], [], [], 0)
                if not r:
                    break
                data, addr = self.stream_sock.recvfrom(2048)
                if not data:
                    break
                self.last_rx_time = time.time()

                # Check if it's a binary packet (RWP 0x5257 or legacy OMP 0xAA55, 9 bytes)
                if len(data) >= 9:
                    is_rwp = (data[0] == 0x57 and data[1] == 0x52)  # little-endian 0x5257 ('W', 'R')
                    is_omp = (data[0] == 0x55 and data[1] == 0xAA)  # little-endian 0xAA55
                    if is_rwp or is_omp:
                        pkt = OMPPacket.unpack(data)
                        if pkt:
                            omp_packets.append(pkt)
                            continue

                # Otherwise handle as ASCII line(s)
                try:
                    text = data.decode('utf-8', errors='ignore').strip()
                    for line in text.split('\n'):
                        line = line.strip()
                        if line:
                            ascii_lines.append(line)
                except Exception:
                    pass
        except BlockingIOError:
            pass
        except Exception as e:
            logging.debug(f"receive_packets error: {e}")

        return (omp_packets, ascii_lines)


class TransportMode:
    NONE = 0
    USB  = 1
    WIFI = 2


class TransportManager:
    """Smart dual-transport router with USB priority, auto-discovery, and seamless failover."""
    def __init__(self):
        self.usb = SerialStreamManager()
        self.wifi = WiFiStreamManager()
        self.mode = TransportMode.NONE

    def set_last_known_ip(self, ip: str):
        if ip and ip != "0.0.0.0":
            self.wifi.last_known_ip = ip

    def auto_discover(self) -> tuple:
        """
        Probes USB ports first. If absent, scans for Wi-Fi UDP beacon.
        Returns (TransportMode, address_string)
        """
        # Priority 1: USB (physical cable to PC)
        for pinfo in SerialStreamManager.list_ports():
            port = pinfo["port"]
            logging.info(f"auto_discover: Probing USB {port}...")
            if SerialStreamManager.probe_port(port):
                logging.info(f"auto_discover: Genuine OmniScroll found on USB {port}")
                return (TransportMode.USB, port)

        # Priority 2: Wi-Fi
        logging.info("auto_discover: Probing WiFi beacons...")
        ip = self.wifi.discover(timeout=2.5)
        if ip:
            logging.info(f"auto_discover: OmniScroll discovered via WiFi at {ip}")
            return (TransportMode.WIFI, ip)

        return (TransportMode.NONE, None)

    def connect(self, mode: int, address: str) -> bool:
        self.disconnect()
        if mode == TransportMode.USB:
            ok = self.usb.connect(address, bypass_check=True)
            if ok:
                self.mode = TransportMode.USB
            return ok
        elif mode == TransportMode.WIFI:
            ok = self.wifi.connect(address)
            if ok:
                self.mode = TransportMode.WIFI
            return ok
        return False

    def is_connected(self) -> bool:
        if self.mode == TransportMode.USB:
            return self.usb.is_connected()
        elif self.mode == TransportMode.WIFI:
            return self.wifi.is_connected()
        return False

    def get_status_text(self) -> str:
        if self.mode == TransportMode.USB:
            return f"USB Cable ({self.usb.active_port})"
        elif self.mode == TransportMode.WIFI:
            return f"Wi-Fi Wireless ({self.wifi.target_ip})"
        return "Disconnected"

    def disconnect(self):
        self.usb.disconnect()
        self.wifi.disconnect()
        self.mode = TransportMode.NONE

    def send_command(self, cmd: str) -> bool:
        if self.mode == TransportMode.USB:
            return self.usb.send_command(cmd)
        elif self.mode == TransportMode.WIFI:
            return self.wifi.send_command(cmd)
        return False
