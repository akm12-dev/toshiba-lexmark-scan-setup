"""Chargement / sauvegarde de la configuration (JSON dans le dossier utilisateur)."""
import json
import logging
import os
import sys
from pathlib import Path

from . import APP_ID

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"


def config_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_scan_folder() -> str:
    if IS_WINDOWS:
        return r"C:\Scans"
    if IS_MAC:
        return "/Users/Shared/Scans"
    return str(Path.home() / "Scans")


DEFAULTS = {
    "brand": "toshiba",  # toshiba | lexmark
    "printer_ip": "",
    # --- Scan vers dossier (SMB) ---
    "share": {
        "folder": default_scan_folder(),
        "share_name": "SCANS",
        "username": "scanner",
        "password": "",
        "create_user": True,
        "open_firewall": True,
        "set_private_network": True,
        "disable_smb_signing": False,
        "enable_smb1": False,
    },
    # --- Serveur SMTP du fournisseur (Gmail, OVH, ...) ---
    "upstream": {
        "provider": "Gmail",
        "host": "smtp.gmail.com",
        "port": 587,
        "security": "starttls",  # starttls | ssl | none
        "username": "",
        "password": "",
        "from_addr": "",
        "test_to": "",
    },
    # --- Relais SMTP local (imprimante -> PC -> fournisseur) ---
    "relay": {
        "mode": "relay",  # relay | direct
        "listen_port": 25,
        "allowed_ips": "",  # vide = réseau local uniquement
        "auth_user": "",
        "auth_password": "",
        "forward_email": True,
        "rewrite_from": True,
        "save_attachments": False,
        "save_folder": str(Path(default_scan_folder()) / "Mail"),
        "subfolder_by_date": True,
        "autostart": False,
    },
}


def _merge(defaults: dict, data: dict) -> dict:
    out = {}
    for k, v in defaults.items():
        if isinstance(v, dict):
            out[k] = _merge(v, data.get(k, {}) if isinstance(data.get(k), dict) else {})
        else:
            out[k] = data.get(k, v)
    return out


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> dict:
    p = config_path()
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # fichier corrompu : on repart des valeurs par défaut
            logging.getLogger(__name__).warning("Configuration illisible (%s), valeurs par défaut utilisées", e)
    return _merge(DEFAULTS, data)


def save(cfg: dict) -> None:
    p = config_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)  # contient des mots de passe : lisible par l'utilisateur seulement
    except OSError:
        pass


def queue_dir() -> Path:
    d = config_dir() / "queue"
    d.mkdir(exist_ok=True)
    return d


def log_file() -> Path:
    return config_dir() / "scansetup.log"
