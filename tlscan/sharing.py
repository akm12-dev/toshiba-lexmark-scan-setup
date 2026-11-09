"""Création du partage réseau (SMB) pour le « Scan vers dossier » sur Windows et macOS.

Les opérations nécessitent les droits administrateur : sous Windows une fenêtre UAC
s'ouvre, sous macOS une demande de mot de passe administrateur.
"""
import getpass
import os
import subprocess
import tempfile
from pathlib import Path

from .config import IS_MAC, IS_WINDOWS

NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def _ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _sh_quote(s: str) -> str:
    return "'" + str(s).replace("'", "'\"'\"'") + "'"


# ============================================================== WINDOWS
def _run_elevated_ps(body: str):
    """Exécute un script PowerShell en administrateur, renvoie (ok, sortie)."""
    tmp = Path(tempfile.mkdtemp(prefix="tlscan_"))
    script, logf = tmp / "setup.ps1", tmp / "setup.log"
    wrapper = (
        "$ErrorActionPreference = 'Stop'\n"
        f"& {{\n try {{\n{body}\n 'RESULT:OK'\n }} catch {{ \"ERREUR : $($_.Exception.Message)\"; 'RESULT:FAIL' }}\n}}"
        f" *>&1 | Out-File -FilePath {_ps_quote(logf)} -Encoding utf8\n"
    )
    script.write_text(wrapper, encoding="utf-8-sig")
    launcher = (
        "Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "
        + _ps_quote(f'-NoProfile -ExecutionPolicy Bypass -File "{script}"')
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", launcher],
                           capture_output=True, text=True, creationflags=NO_WINDOW)
        out = logf.read_text(encoding="utf-8-sig", errors="replace") if logf.exists() else ""
        if r.returncode != 0 and not out:
            return False, "Opération annulée ou droits administrateur refusés.\n" + (r.stderr or "")
        ok = "RESULT:OK" in out
        out = out.replace("RESULT:OK", "").replace("RESULT:FAIL", "").strip()
        return ok, out
    finally:
        for f in (script, logf):
            try:
                f.unlink()  # le script contenait le mot de passe
            except OSError:
                pass
        try:
            tmp.rmdir()
        except OSError:
            pass


def _windows_create(s: dict):
    owner = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}".lstrip("\\")
    body = f"""
$user = {_ps_quote(s['username'])}; $pass = {_ps_quote(s['password'])}
$folder = {_ps_quote(s['folder'])}; $share = {_ps_quote(s['share_name'])}; $owner = {_ps_quote(owner)}
if (${'true' if s['create_user'] else 'false'}) {{
  $sec = ConvertTo-SecureString $pass -AsPlainText -Force
  if (Get-LocalUser -Name $user -ErrorAction SilentlyContinue) {{
    Set-LocalUser -Name $user -Password $sec -PasswordNeverExpires $true
    Enable-LocalUser -Name $user
    "Compte local '$user' existant : mot de passe mis à jour."
  }} else {{
    New-LocalUser -Name $user -Password $sec -PasswordNeverExpires -UserMayNotChangePassword `
      -FullName 'Scan MFP' -Description 'Compte dedie au scan Toshiba Lexmark' | Out-Null
    "Compte local '$user' créé."
  }}
  $k = 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon\\SpecialAccounts\\UserList'
  if (-not (Test-Path $k)) {{ New-Item -Path $k -Force | Out-Null }}
  New-ItemProperty -Path $k -Name $user -Value 0 -PropertyType DWord -Force | Out-Null
  "Compte masqué de l'écran de connexion."
}}
New-Item -ItemType Directory -Force -Path $folder | Out-Null
"Dossier prêt : $folder"
$grant = "$($user):(OI)(CI)M"
& icacls $folder /grant $grant /T /Q | Out-Null
if ($LASTEXITCODE -ne 0) {{ throw "icacls a échoué (droits NTFS)" }}
"Droits NTFS 'Modification' accordés à $user."
$admins = (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')).Translate([System.Security.Principal.NTAccount]).Value
if (Get-SmbShare -Name $share -ErrorAction SilentlyContinue) {{ Remove-SmbShare -Name $share -Force; "Ancien partage '$share' remplacé." }}
$full = @($admins)
if ($owner -and ($owner.Split('\\')[-1] -ne $user)) {{ $full += $owner }}
New-SmbShare -Name $share -Path $folder -FullAccess $full -ChangeAccess $user | Out-Null
"Partage \\\\$env:COMPUTERNAME\\$share créé."
if (${'true' if s['set_private_network'] else 'false'}) {{
  Get-NetConnectionProfile | Where-Object {{ $_.NetworkCategory -eq 'Public' }} | ForEach-Object {{
    Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private
    "Réseau '$($_.Name)' passé en profil Privé."
  }}
}}
if (${'true' if s['open_firewall'] else 'false'}) {{
  Enable-NetFirewallRule -Group '@FirewallAPI.dll,-28502' -ErrorAction SilentlyContinue
  Set-NetFirewallRule -Group '@FirewallAPI.dll,-28502' -Profile Private,Domain -ErrorAction SilentlyContinue
  "Pare-feu : « Partage de fichiers et d'imprimantes » autorisé (réseaux privés)."
}}
if (${'true' if s['disable_smb_signing'] else 'false'}) {{
  Set-SmbServerConfiguration -RequireSecuritySignature $false -Force
  "Signature SMB obligatoire désactivée (compatibilité anciens multifonctions)."
}}
if (${'true' if s['enable_smb1'] else 'false'}) {{
  try {{
    Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol-Server -NoRestart -All | Out-Null
    "SMB1 activé (redémarrage du PC nécessaire)."
  }} catch {{ "SMB1 indisponible sur ce Windows : $($_.Exception.Message)" }}
}}
"""
    return _run_elevated_ps(body)


def _windows_remove(s: dict, delete_user: bool):
    body = f"""
$share = {_ps_quote(s['share_name'])}; $user = {_ps_quote(s['username'])}
if (Get-SmbShare -Name $share -ErrorAction SilentlyContinue) {{ Remove-SmbShare -Name $share -Force; "Partage '$share' supprimé." }}
else {{ "Aucun partage nommé '$share'." }}
if (${'true' if delete_user else 'false'}) {{
  if (Get-LocalUser -Name $user -ErrorAction SilentlyContinue) {{ Remove-LocalUser -Name $user; "Compte '$user' supprimé." }}
}}
"Le dossier et les fichiers scannés sont conservés."
"""
    return _run_elevated_ps(body)


# ============================================================== macOS
def _run_elevated_sh(body: str):
    fd, path = tempfile.mkstemp(prefix="tlscan_", suffix=".sh")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\nset -u\n" + body + "\n")
    os.chmod(path, 0o700)
    try:
        r = subprocess.run(
            ["osascript",
             "-e", "on run argv",
             "-e", 'do shell script "/bin/bash " & quoted form of (item 1 of argv) & " 2>&1" '
                   'with prompt "Toshiba Lexmark Scan Setup doit configurer le partage de fichiers." '
                   "with administrator privileges",
             "-e", "end run", path],
            capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 and "RESULT:" not in out:
            return False, "Opération annulée ou mot de passe administrateur refusé.\n" + out
        ok = "RESULT:OK" in out
        return ok, out.replace("RESULT:OK", "").replace("RESULT:FAIL", "").replace("\r", "\n").strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _mac_create(s: dict):
    u, p, folder, share = (_sh_quote(s[k]) for k in ("username", "password", "folder", "share_name"))
    create = "1" if s["create_user"] else "0"
    body = f"""
U={u}; P={p}; FOLDER={folder}; SHARE={share}
fail() {{ echo "ERREUR : $1"; echo RESULT:FAIL; exit 1; }}
if [ "{create}" = 1 ]; then
  if id "$U" >/dev/null 2>&1; then
    dscl . -passwd "/Users/$U" "$P" || fail "mise à jour du mot de passe impossible"
    echo "Compte '$U' existant : mot de passe mis à jour."
  else
    sysadminctl -addUser "$U" -fullName "Scan MFP" -password "$P" -home /var/empty >/dev/null 2>&1
    id "$U" >/dev/null 2>&1 || fail "création du compte '$U' impossible"
    echo "Compte de partage '$U' créé."
  fi
  dscl . -create "/Users/$U" UserShell /usr/bin/false
  dscl . -create "/Users/$U" IsHidden 1
  pwpolicy -u "$U" -sethashtypes SMB-NT on >/dev/null 2>&1
  dscl . -passwd "/Users/$U" "$P"
  echo "Accès « Partage Windows » (SMB) activé pour '$U'."
fi
dseditgroup -o read com.apple.access_smb >/dev/null 2>&1 && dseditgroup -o edit -a "$U" -t user com.apple.access_smb
mkdir -p "$FOLDER" || fail "création du dossier impossible"
chmod +a "$U allow list,add_file,search,add_subdirectory,delete_child,readattr,writeattr,readextattr,writeextattr,readsecurity,file_inherit,directory_inherit" "$FOLDER" \
  || fail "droits sur le dossier impossibles"
echo "Dossier prêt : $FOLDER (droits d'écriture pour $U)"
sharing -r "$SHARE" >/dev/null 2>&1
sharing -a "$FOLDER" -S "$SHARE" -s 001 -g 000 >/dev/null 2>&1 || sharing -a "$FOLDER" -S "$SHARE" \
  || fail "création du partage impossible"
echo "Partage SMB '$SHARE' créé."
defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server EnabledServices -array disk
launchctl enable system/com.apple.smbd 2>/dev/null
launchctl load -w /System/Library/LaunchDaemons/com.apple.smbd.plist 2>/dev/null
launchctl kickstart -k system/com.apple.smbd 2>/dev/null
echo "Service de partage de fichiers SMB activé."
echo RESULT:OK
"""
    return _run_elevated_sh(body)


def _mac_remove(s: dict, delete_user: bool):
    body = f"""
SHARE={_sh_quote(s['share_name'])}; U={_sh_quote(s['username'])}
sharing -r "$SHARE" && echo "Partage '$SHARE' supprimé." || echo "Aucun partage nommé '$SHARE'."
if [ "{1 if delete_user else 0}" = 1 ] && id "$U" >/dev/null 2>&1; then
  sysadminctl -deleteUser "$U" >/dev/null 2>&1 && echo "Compte '$U' supprimé."
fi
echo "Le dossier et les fichiers scannés sont conservés."
echo RESULT:OK
"""
    return _run_elevated_sh(body)


# ============================================================== API
def validate(s: dict):
    errors = []
    if not s.get("folder"):
        errors.append("Choisissez un dossier de destination.")
    name = s.get("share_name", "")
    if not name or any(c in name for c in '\\/:*?"<>| ') or len(name) > 80:
        errors.append("Nom de partage invalide (pas d'espaces ni de caractères spéciaux).")
    if not s.get("username") or any(c in s["username"] for c in '\\/:*?"<>|@[];,=+ '):
        errors.append("Nom d'utilisateur invalide (lettres et chiffres conseillés, ex : scanner).")
    if s.get("create_user") and len(s.get("password", "")) < 8:
        errors.append("Mot de passe : 8 caractères minimum.")
    if any(c in s.get("password", "") for c in "\"'\\"):
        errors.append("Évitez les guillemets et l'antislash dans le mot de passe (mal gérés par certains multifonctions).")
    return errors


def create_share(s: dict):
    if IS_WINDOWS:
        return _windows_create(s)
    if IS_MAC:
        return _mac_create(s)
    return False, "Système non pris en charge (Windows ou macOS uniquement)."


def remove_share(s: dict, delete_user: bool = False):
    if IS_WINDOWS:
        return _windows_remove(s, delete_user)
    if IS_MAC:
        return _mac_remove(s, delete_user)
    return False, "Système non pris en charge."


def check_share(s: dict, ip: str):
    """Vérifications sans droits admin : port 445 joignable et partage visible."""
    from . import netutil
    lines, ok = [], True
    if netutil.port_open(ip, 445):
        lines.append(f"✔ Port SMB 445 ouvert sur {ip}")
    else:
        ok = False
        lines.append(f"✘ Port SMB 445 fermé sur {ip} (partage désactivé ou pare-feu)")
    if IS_WINDOWS:
        unc = rf"\\localhost\{s['share_name']}"
        if os.path.isdir(unc):
            lines.append(f"✔ Partage {unc} accessible")
        else:
            ok = False
            lines.append(f"✘ Partage {unc} introuvable")
    elif IS_MAC:
        try:
            r = subprocess.run(["sharing", "-l"], capture_output=True, text=True, timeout=10)
            if s["share_name"] in r.stdout:
                lines.append(f"✔ Partage « {s['share_name']} » déclaré")
        except Exception:
            pass
    if os.path.isdir(s["folder"]):
        lines.append(f"✔ Dossier {s['folder']} présent")
    else:
        ok = False
        lines.append(f"✘ Dossier {s['folder']} absent")
    return ok, "\n".join(lines)
