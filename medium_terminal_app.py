import platform
import socket
import subprocess
import ipaddress
from concurrent.futures import ThreadPoolExecutor


def get_my_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        # Unpack the (ip, port) tuple directly into two variables
        ip_address, _ = s.getsockname()
        return ip_address


def check_gateway(ip):
    # 1. Try a quick TCP probe on common router/management ports
    for port in (80, 443, 22, 53, 8080):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((ip, port)) in (0, 111, 10061):
                return ip, f"TCP Port {port}"

    # 2. Fallback to a single fast ICMP ping
    is_windows = platform.system().lower() == "windows"
    cmd = ["ping", "-n", "1", "-w", "250", ip] if is_windows else ["ping", "-c", "1", "-W", "1", ip]
    if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return ip, "ICMP Ping"

    return ip, None


if __name__ == "__main__":
    my_ip = get_my_ip()
    first_octet, second_octet, third_octet, fourth_octet = my_ip.split(".")
    print(f"Your IP: {my_ip}")

    # Build a list of gateway candidates (.1 and .254) across your second and third octets
    candidates = set()
    for third in range(0, 256):
        candidates.add(f"172.{second_octet}.{third}.1")
        candidates.add(f"172.{second_octet}.{third}.254")

    for second in range(0, 100):
        candidates.add(f"172.{second}.1.1")
        candidates.add(f"172.{second}.0.1")

    candidates.discard(my_ip)
    candidates = sorted(candidates)

    print(f"Sweeping {len(candidates)} potential 10.x.x.x VLAN gateways...")

    active_vlans = []
    with ThreadPoolExecutor(max_workers=500) as executor:
        for ip, method in executor.map(check_gateway, candidates):
            if method:
                print(f"[+] Active VLAN Gateway: {ip:<15} (via {method})")
                active_vlans.append(ip)

    print(f"\nFound {len(active_vlans)} reachable VLAN gateways.")
    with open("active_gateways.txt", "w") as f:
        for gw in active_vlans:
            f.write(f"{gw}\n")
    print("Saved all 146 gateways to active_gateways.txt")





# Common static/DHCP host offsets where servers, printers, and active devices usually sit
SAMPLE_OFFSETS = (2, 5, 10, 20, 50, 100, 150, 200, 250, 253)


def check_ip(ip):
    for port in (80, 443, 22, 445, 3389, 9100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.15)
            if s.connect_ex((ip, port)) in (0, 111, 10061):
                return ip, f"TCP:{port}"

    is_windows = platform.system().lower() == "windows"
    cmd = ["ping", "-n", "1", "-w", "200", ip] if is_windows else ["ping", "-c", "1", "-W", "1", ip]
    if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return ip, "ICMP"

    return ip, None


with open("active_gateways.txt") as f:
    gateways = [line.strip() for line in f if line.strip()]

# Build 10 sample target IPs behind every single one of your 146 gateways
sample_targets = []
for gw in gateways:
    first, second, third, _ = gw.split(".")
    for offset in SAMPLE_OFFSETS:
        sample_targets.append(f"{first}.{second}.{third}.{offset}")

print(f"Spot-checking {len(sample_targets)} sample hosts across {len(gateways)} VLANs...")

populated_vlans = set()
with ThreadPoolExecutor(max_workers=500) as executor:
    for ip, method in executor.map(check_ip, sample_targets):
        if method:
            first, second, third, _ = ip.split(".")
            vlan_prefix = f"{first}.{second}.{third}.0/24"
            populated_vlans.add(vlan_prefix)
            print(f"[+] Hit in {vlan_prefix:<16} -> {ip:<15} ({method})")

print(f"\nFound {len(populated_vlans)} populated VLANs with active devices behind the gateway:")
for vlan in sorted(populated_vlans):
    print(f"  - {vlan}")

sorted_vlans = sorted(populated_vlans)

print(f"\nFound {len(sorted_vlans)} populated VLANs with active devices behind the gateway:")
for vlan in sorted_vlans:
    print(f"  - {vlan}")

# Save the populated VLAN subnets to a file for the full scanner
with open("populated_vlans.txt", "w") as f:
    for vlan in sorted_vlans:
        f.write(f"{vlan}\n")

print("\nSaved populated subnets to populated_vlans.txt")









import socket
import platform
import subprocess
import ipaddress
import re
import errno

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


# ==========================================
# CONFIGURATION
# ==========================================

VLAN_FILE = Path("populated_vlans.txt")
OUTPUT_FILE = Path("network_map.txt")

MAX_WORKERS = 500
SOCKET_TIMEOUT = 0.3

# Common ports and their associated services

PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    139: "NetBIOS",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    554: "RTSP",
    631: "IPP",
    3306: "MySQL",
    3389: "RDP",
    5000: "HTTP-Alt",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
    9100: "Printer"
}

# Ports used for the initial alive check

CHECK_PORTS = (22, 80, 443, 445, 3389, 9100)


# ==========================================
# OPTIONAL MANUFACTURER DATABASE
# ==========================================

try:
    from manuf import MacParser

    mac_parser = MacParser()

except ImportError:
    mac_parser = None
    print("Manufacturer lookup unavailable.")
    print("Install it using: pip install manuf\n")


# ==========================================
# HOST DISCOVERY
# ==========================================

def is_host_alive(ip):

    # TCP check

    for port in CHECK_PORTS:

        try:
            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            ) as s:

                s.settimeout(SOCKET_TIMEOUT)

                result = s.connect_ex((ip, port))

                if result in (
                    0,
                    errno.ECONNREFUSED,
                    10061
                ):
                    return ip, f"TCP:{port}"

        except OSError:
            pass

    # ICMP fallback

    is_windows = platform.system().lower() == "windows"

    if is_windows:

        cmd = ["ping", "-n", "1", "-w", "500", ip]

    else:

        cmd = ["ping", "-c", "1", "-W", "1", ip]

    try:

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )

        if result.returncode == 0:
            return ip, "ICMP"

    except (subprocess.TimeoutExpired, OSError):
        pass

    return ip, None


# ==========================================
# MAC ADDRESS DISCOVERY
# ==========================================

def get_mac_address(ip):

    system = platform.system().lower()

    try:

        if system == "windows":

            result = subprocess.run(
                ["arp", "-a", ip],
                capture_output=True,
                text=True,
                timeout=2
            )

            output = result.stdout

        else:

            result = subprocess.run(
                ["ip", "neigh", "show", ip],
                capture_output=True,
                text=True,
                timeout=2
            )

            output = result.stdout

        mac_match = re.search(
            r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}",
            output
        )

        if mac_match:

            return mac_match.group(0).replace("-", ":").lower()

    except (subprocess.TimeoutExpired, OSError):
        pass

    return "Unknown"


# ==========================================
# MANUFACTURER LOOKUP
# ==========================================

def get_manufacturer(mac):

    if mac == "Unknown":
        return "Unknown"

    if mac_parser is None:
        return "Unavailable (install manuf)"

    try:

        manufacturer = mac_parser.get_manuf(mac)

        if manufacturer:
            return manufacturer

    except Exception:
        pass

    return "Unknown"


# ==========================================
# HOSTNAME DISCOVERY
# ==========================================

def get_hostname(ip):

    try:

        hostname = socket.gethostbyaddr(ip)[0]

        return hostname

    except (socket.herror, socket.gaierror, OSError):
        return "Unknown"


# ==========================================
# OPEN PORT DISCOVERY
# ==========================================

def get_open_ports(ip):

    open_ports = []

    for port, service in PORTS.items():

        try:

            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            ) as s:

                s.settimeout(SOCKET_TIMEOUT)

                if s.connect_ex((ip, port)) == 0:

                    open_ports.append(
                        f"{port}/{service}"
                    )

        except OSError:
            pass

    return open_ports


# ==========================================
# BASIC DEVICE CLASSIFICATION
# ==========================================

def identify_device(open_ports, hostname, manufacturer):

    ports = [
        int(item.split("/")[0])
        for item in open_ports
    ]

    hostname_lower = hostname.lower()
    manufacturer_lower = manufacturer.lower()

    if 9100 in ports or 631 in ports:
        return "Possible Printer"

    if 554 in ports:
        return "Possible IP Camera / Media Device"

    if 445 in ports or 3389 in ports:
        return "Possible Windows Computer"

    if 22 in ports and 80 in ports:
        return "Possible Linux / Network Device"

    if 22 in ports:
        return "Possible SSH Device"

    if 80 in ports or 443 in ports:
        return "Possible Web Server / Network Device"

    if "router" in hostname_lower or "gateway" in hostname_lower:
        return "Possible Router"

    if "cisco" in manufacturer_lower:
        return "Possible Cisco Network Device"

    return "Unknown Device"


# ==========================================
# COMPLETE DEVICE INFORMATION
# ==========================================

def get_device_info(ip, method):

    print(f"Gathering information for {ip}...")

    mac = get_mac_address(ip)

    manufacturer = get_manufacturer(mac)

    hostname = get_hostname(ip)

    open_ports = get_open_ports(ip)

    device_type = identify_device(
        open_ports,
        hostname,
        manufacturer
    )

    return {
        "ip": ip,
        "method": method,
        "mac": mac,
        "manufacturer": manufacturer,
        "hostname": hostname,
        "open_ports": open_ports,
        "device_type": device_type
    }


# ==========================================
# SCAN INDIVIDUAL DEVICE
# ==========================================

def scan_device(ip):

    ip, method = is_host_alive(ip)

    if method is None:
        return None

    return get_device_info(ip, method)


# ==========================================
# PRINT AND SAVE DEVICE INFORMATION
# ==========================================

def save_device(info, out_file):

    ip = info["ip"]

    print(f"\n[+] {ip}")
    print(f"    Detection:    {info['method']}")
    print(f"    Hostname:     {info['hostname']}")
    print(f"    MAC Address:  {info['mac']}")
    print(f"    Manufacturer: {info['manufacturer']}")
    print(f"    Device Type:  {info['device_type']}")

    if info["open_ports"]:

        print("    Open Ports:   " + ", ".join(info["open_ports"]))

    else:

        print("    Open Ports:   None detected")

    out_file.write(f"  [+] {ip:<15} ({info['method']})\n")

    out_file.write(f"      Hostname:     {info['hostname']}\n")
    out_file.write(f"      MAC Address:  {info['mac']}\n")
    out_file.write(f"      Manufacturer: {info['manufacturer']}\n")
    out_file.write(f"      Device Type:  {info['device_type']}\n")

    if info["open_ports"]:

        out_file.write(
            f"      Open Ports:   {', '.join(info['open_ports'])}\n"
        )

    else:

        out_file.write("      Open Ports:   None detected\n")


# ==========================================
# MAIN SCANNER
# ==========================================

if __name__ == "__main__":

    if not VLAN_FILE.exists():

        print("Error: populated_vlans.txt not found.")
        raise SystemExit(1)

    with open(VLAN_FILE, encoding="utf-8") as f:

        vlans = [
            line.strip()
            for line in f
            if line.strip()
        ]

    print(f"Loaded {len(vlans)} populated VLANs.\n")

    total_devices = 0

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as out_file:

        for vlan in vlans:

            try:

                network = ipaddress.IPv4Network(
                    vlan,
                    strict=False
                )

            except ValueError:

                print(f"Invalid VLAN: {vlan}")
                continue

            hosts = [
                str(ip)
                for ip in network.hosts()
            ]

            print(f"\n--- Scanning {vlan} ({len(hosts)} hosts) ---")

            out_file.write(
                f"\n=== VLAN {vlan} ===\n"
            )

            vlan_count = 0

            with ThreadPoolExecutor(
                max_workers=MAX_WORKERS
            ) as executor:

                results = executor.map(
                    scan_device,
                    hosts
                )

                for info in results:

                    if info is None:
                        continue

                    save_device(info, out_file)

                    vlan_count += 1
                    total_devices += 1

            print(
                f"\nSubtotal for {vlan}: {vlan_count} devices\n"
            )

    print("\n================================")
    print("SCAN COMPLETE")
    print("================================")

    print(f"VLANs scanned: {len(vlans)}")
    print(f"Devices found: {total_devices}")

    print(f"\nResults saved to: {OUTPUT_FILE}")

