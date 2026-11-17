
import concurrent.futures
import ipaddress
import re
import socket
import subprocess
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================

APP_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = APP_DIR / "network_map.txt"

MAX_WORKERS = 64

PORTS = [
    22, 80, 443, 445, 554,
    3389, 8000, 8080, 8443, 9100
]


# ==========================================
# NETWORK DETECTION
# ==========================================

def get_local_network():
    try:
        route = subprocess.check_output(
            ["ip", "route", "get", "1.1.1.1"],
            text=True
        )

        match = re.search(r"\bdev\s+(\S+)", route)
        if not match:
            raise RuntimeError("Could not identify network interface.")

        interface = match.group(1)

        addresses = subprocess.check_output(
            ["ip", "-o", "-f", "inet", "addr", "show", "dev", interface],
            text=True
        )

        for line in addresses.splitlines():
            match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", line)

            if match:
                address = ipaddress.ip_interface(match.group(1))

                if address.ip.is_private:
                    return address

        raise RuntimeError("No private IPv4 address found.")

    except FileNotFoundError:
        raise RuntimeError("Linux 'ip' command was not found.")
    except subprocess.CalledProcessError:
        raise RuntimeError("Could not detect your network.")


def get_scan_network(interface):
    network = interface.network

    # Limit large networks to the /24 containing this computer.
    if network.prefixlen < 24:
        network = ipaddress.ip_network(
            f"{interface.ip}/24",
            strict=False
        )

    return network


# ==========================================
# DEVICE DISCOVERY
# ==========================================

def check_ping(ip):
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", str(ip)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )

        return result.returncode == 0

    except (subprocess.TimeoutExpired, OSError):
        return False


def check_ports(ip):
    open_ports = []

    for port in PORTS:
        try:
            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            ) as sock:

                sock.settimeout(0.2)

                if sock.connect_ex((str(ip), port)) == 0:
                    open_ports.append(port)

        except OSError:
            pass

    return open_ports


def get_hostname(ip):
    try:
        return socket.gethostbyaddr(str(ip))[0]
    except (socket.herror, socket.gaierror, OSError):
        return "Unknown"


def get_mac(ip):
    try:
        result = subprocess.check_output(
            ["ip", "neigh", "show", str(ip)],
            text=True,
            stderr=subprocess.DEVNULL
        )

        match = re.search(
            r"\blladdr\s+([0-9a-fA-F:]{17})",
            result
        )

        return match.group(1).upper() if match else "Unknown"

    except (subprocess.CalledProcessError, OSError):
        return "Unknown"


def identify_device(ip, open_ports, local_ip):
    if ip == local_ip:
        return "This Computer"

    if 554 in open_ports:
        return "Possible IP Camera"

    if 9100 in open_ports:
        return "Possible Printer"

    if 3389 in open_ports:
        return "Possible Windows Computer"

    if 445 in open_ports:
        return "Possible Windows Device"

    if 22 in open_ports:
        return "Possible Linux/SSH Device"

    if 80 in open_ports or 443 in open_ports:
        return "Possible Web Device"

    return "Unknown Device"


def scan_device(ip, local_ip):
    ping_alive = check_ping(ip)
    open_ports = check_ports(ip)

    # Always include this computer.
    if not ping_alive and not open_ports and ip != local_ip:
        return None

    if ip == local_ip:
        method = "This PC"
    elif ping_alive:
        method = "ICMP"
    else:
        method = "TCP"

    hostname = get_hostname(ip)
    mac = get_mac(ip)

    device_type = identify_device(
        ip,
        open_ports,
        local_ip
    )

    return {
        "ip": str(ip),
        "method": method,
        "hostname": hostname,
        "mac": mac,
        "device_type": device_type,
        "ports": ", ".join(map(str, open_ports)) if open_ports else "None detected"
    }


# ==========================================
# MAIN SCANNER
# ==========================================

def main():
    print("=" * 45)
    print("          BASIC LAN SCANNER")
    print("=" * 45)

    try:
        interface = get_local_network()
        network = get_scan_network(interface)

    except Exception as error:
        print(f"\nNetwork detection failed: {error}")
        input("\nPress Enter to exit...")
        return

    local_ip = interface.ip

    print(f"\nYour IP:       {local_ip}")
    print(f"Network:      {network}")
    print(f"Scanning:     {network.num_addresses - 2} possible devices")
    print("\nScanning... Please wait.\n")

    devices = []

    hosts = list(network.hosts())

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(scan_device, ip, local_ip): ip
            for ip in hosts
        }

        total = len(futures)

        for completed, future in enumerate(
            concurrent.futures.as_completed(futures), 1
        ):
            try:
                result = future.result()

                if result:
                    devices.append(result)

                    print(
                        f"[+] {result['ip']} "
                        f"({result['method']}) "
                        f"- {result['hostname']}"
                    )

            except Exception as error:
                print(f"Device scan error: {error}")

            if completed % 25 == 0 or completed == total:
                print(f"Progress: {completed}/{total}")

    devices.sort(
        key=lambda device: ipaddress.ip_address(device["ip"])
    )

    # ==========================================
    # SAVE NETWORK MAP
    # ==========================================

    report = [
        f"=== VLAN {network} ===",
        ""
    ]

    for device in devices:
        report.extend([
            f"  [+] {device['ip']} ({device['method']})",
            f"      Hostname:     {device['hostname']}",
            f"      MAC Address:  {device['mac']}",
            f"      Manufacturer: Unknown",
            f"      Device Type:  {device['device_type']}",
            f"      Open Ports:   {device['ports']}",
            ""
        ])

    OUTPUT_FILE.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    print("\n" + "=" * 45)
    print("SCAN COMPLETE")
    print("=" * 45)

    print(f"Network: {network}")
    print(f"Devices found: {len(devices)}")
    print(f"Saved to: {OUTPUT_FILE}")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
