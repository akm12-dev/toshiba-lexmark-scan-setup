"""Démarrage automatique du relais SMTP à l'ouverture de session + règle de pare-feu."""
import os
import subprocess
import sys
from pathlib import Path

from .config import IS_MAC, IS_WINDOWS

LABEL = "com.tlscansetup.relay"
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def _command():
    """Programme + arguments pour lancer le relais sans interface."""
    if getattr(sys, "frozen", False):  # version compilée (.exe / .app)
        return sys.executable, ["--relay"]
    script = str(Path(__file__).resolve().parent.parent / "ToshibaLexmarkScanSetup.py")
    exe = sys.executable
    if IS_WINDOWS:
        w = Path(exe).with_name("pythonw.exe")
        if w.exists():
            exe = str(w)
    return exe, [script, "--relay"]


def _win_shortcut() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/Toshiba Lexmark Scan Relay.lnk"


def _mac_plist() -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"


def enable():
    exe, args = _command()
    if IS_WINDOWS:
        lnk = _win_shortcut()
        arg_str = " ".join(f'"{a}"' for a in args)
        ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{str(lnk).replace(chr(39), chr(39)*2)}');"
              f"$s.TargetPath='{exe.replace(chr(39), chr(39)*2)}';"
              f"$s.Arguments='{arg_str.replace(chr(39), chr(39)*2)}';"
              f"$s.WorkingDirectory='{str(Path(args[0]).parent if args[0] != '--relay' else Path(exe).parent).replace(chr(39), chr(39)*2)}';"
              "$s.WindowStyle=7;$s.Description='Relais SMTP Toshiba Lexmark Scan';$s.Save()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True,
                       creationflags=NO_WINDOW)
        return f"Raccourci de démarrage créé : {lnk}"
    if IS_MAC:
        p = _mac_plist()
        p.parent.mkdir(parents=True, exist_ok=True)
        items = "".join(f"<string>{a}</string>" for a in [exe] + args)
        p.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{LABEL}</string>
<key>ProgramArguments</key><array>{items}</array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
</dict></plist>
""", encoding="utf-8")
        return f"Agent de démarrage créé : {p} (actif à la prochaine ouverture de session)"
    raise OSError("Système non pris en charge")


def disable():
    if IS_WINDOWS:
        _win_shortcut().unlink(missing_ok=True)
    elif IS_MAC:
        p = _mac_plist()
        if p.exists():
            subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
            p.unlink()
    return "Démarrage automatique désactivé"


def is_enabled() -> bool:
    if IS_WINDOWS:
        return _win_shortcut().exists()
    if IS_MAC:
        return _mac_plist().exists()
    return False


def open_firewall_port(port: int):
    """Autorise le port du relais dans le pare-feu Windows (réseaux privés). macOS : pas nécessaire
    (le pare-feu applicatif demande l'autorisation au premier lancement)."""
    if not IS_WINDOWS:
        return True, "macOS : acceptez la demande « Autoriser les connexions entrantes » au premier démarrage du relais."
    from .sharing import _run_elevated_ps
    body = f"""
Get-NetFirewallRule -DisplayName 'Toshiba Lexmark Scan Relay SMTP' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'Toshiba Lexmark Scan Relay SMTP' -Direction Inbound -Protocol TCP -LocalPort {int(port)} `
  -Action Allow -Profile Private,Domain | Out-Null
"Pare-feu : port TCP {int(port)} autorisé en entrée (réseaux privés)."
"""
    return _run_elevated_ps(body)
