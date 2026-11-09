"""Outils réseau : IP locale, test de ports, plages autorisées."""
import ipaddress
import socket
import subprocess
import sys


def local_ip() -> str:
    """IP de ce PC sur le réseau local (celle que l'imprimante doit joindre)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # aucun paquet n'est envoyé (UDP)
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


def hostname() -> str:
    return socket.gethostname()


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ping(host: str) -> bool:
    flag = "-n" if sys.platform.startswith("win") else "-c"
    try:
        kwargs = {}
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        r = subprocess.run(["ping", flag, "1", host], capture_output=True, timeout=6, **kwargs)
        return r.returncode == 0
    except Exception:
        return False


def parse_allowed(spec: str):
    """'192.168.1.50, 10.0.0.0/24' -> liste de réseaux. Vide -> réseaux privés + localhost."""
    nets = []
    for part in (spec or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        nets.append(ipaddress.ip_network(part, strict=False))
    return nets


def ip_allowed(ip: str, nets) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    if addr.is_loopback:
        return True
    if not nets:
        return addr.is_private or addr.is_link_local
    return any(addr in n for n in nets)
