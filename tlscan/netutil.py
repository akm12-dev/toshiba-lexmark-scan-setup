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


# --------------------------------------------------------------- FILE_SHARE (Toshiba)
FILE_SHARE = "FILE_SHARE"

# Codes d'erreur Windows rencontrés en ouvrant \IP\PARTAGE
_UNC_ERRORS = {
    5: "auth", 86: "auth", 1326: "auth", 1327: "auth", 1331: "auth", 1909: "auth",
    1272: "guest_blocked",
    53: "unreachable", 64: "unreachable", 1231: "unreachable",
    67: "no_share", 2: "no_share", 3: "no_share",
}


def check_unc(host: str, share: str = FILE_SHARE) -> tuple:
    r"""Tente de lister \\host\share sans identifiants particuliers.

    Retourne (statut, détail) avec statut parmi :
    ok, auth (Windows demande un nom d'utilisateur / mot de passe), guest_blocked,
    unreachable, no_share, no_smb (port 445 fermé), error.
    """
    if not port_open(host, 445, timeout=3):
        return "no_smb", "le port 445 (SMB) de l'imprimante ne répond pas"
    import os
    path = f"\\\\{host}\\{share}"
    try:
        n = len(os.listdir(path))
        return "ok", f"{n} élément(s) dans {path}"
    except OSError as e:
        code = getattr(e, "winerror", None)
        return _UNC_ERRORS.get(code, "auth" if isinstance(e, PermissionError) else "error"), \
            f"{e.strerror or e} (code {code if code is not None else e.errno})"
