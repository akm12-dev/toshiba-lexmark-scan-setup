"""Envoi vers le serveur SMTP du fournisseur, enregistrement des pièces jointes, file d'attente."""
import json
import logging
import re
import smtplib
import ssl
import time
import uuid
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, make_msgid
from pathlib import Path

from . import config

log = logging.getLogger("tlscan.mail")

# Fournisseur -> (serveur, port, sécurité, remarque)
PROVIDERS = {
    "Gmail": ("smtp.gmail.com", 587, "starttls",
              "Validation en 2 étapes obligatoire + mot de passe d'application (myaccount.google.com/apppasswords)."),
    "Outlook.com / Hotmail": ("smtp-mail.outlook.com", 587, "starttls",
                              "Microsoft a restreint l'authentification SMTP par mot de passe : si le test échoue, utilisez un autre fournisseur."),
    "Microsoft 365": ("smtp.office365.com", 587, "starttls",
                      "SMTP AUTH doit être activé sur la boîte. Microsoft retire l'authentification de base : préférez un autre fournisseur si refus."),
    "OVH (MX Plan / Email Pro)": ("ssl0.ovh.net", 465, "ssl", "Identifiant = adresse e-mail complète."),
    "IONOS": ("smtp.ionos.fr", 465, "ssl", "Identifiant = adresse e-mail complète."),
    "Infomaniak": ("mail.infomaniak.com", 465, "ssl", "Identifiant = adresse e-mail complète."),
    "Orange": ("smtp.orange.fr", 465, "ssl", "Identifiant = adresse Orange complète."),
    "Free": ("smtp.free.fr", 465, "ssl", "Identifiant = adresse Free complète."),
    "SFR": ("smtp.sfr.fr", 465, "ssl", "Identifiant = adresse SFR complète."),
    "Yahoo": ("smtp.mail.yahoo.com", 465, "ssl", "Mot de passe d'application requis."),
    "iCloud": ("smtp.mail.me.com", 587, "starttls", "Mot de passe pour application requis (appleid.apple.com)."),
    "Personnalisé": ("", 587, "starttls", "Renseignez les paramètres fournis par votre hébergeur."),
}

SECURITY_LABELS = {"starttls": "STARTTLS", "ssl": "SSL/TLS", "none": "Aucune"}


def _connect(up: dict) -> smtplib.SMTP:
    host, port, sec = up["host"].strip(), int(up["port"]), up.get("security", "starttls")
    if not host:
        raise ValueError("Serveur SMTP du fournisseur non renseigné")
    ctx = ssl.create_default_context()
    if sec == "ssl":
        s = smtplib.SMTP_SSL(host, port, timeout=60, context=ctx)
    else:
        s = smtplib.SMTP(host, port, timeout=60)
        s.ehlo()
        if sec == "starttls":
            s.starttls(context=ctx)
            s.ehlo()
    if up.get("username"):
        s.login(up["username"], up.get("password", ""))
    return s


def send_upstream(up: dict, relay: dict, mail_from: str, rcpts: list, raw: bytes) -> None:
    """Transmet un message reçu de l'imprimante au serveur du fournisseur (lève une exception si échec)."""
    envelope_from = (up.get("from_addr") or up.get("username") or mail_from).strip()
    to_send = raw
    if relay.get("rewrite_from", True) and envelope_from:
        try:
            msg = BytesParser(policy=policy.SMTP).parsebytes(raw)
            original = msg.get("From")
            if msg.get("From") is not None:
                del msg["From"]
            msg["From"] = envelope_from
            if original and msg.get("Reply-To") is None and envelope_from.lower() not in str(original).lower():
                msg["Reply-To"] = str(original)
            if msg.get("Date") is None:
                msg["Date"] = formatdate(localtime=True)
            if msg.get("Message-ID") is None:
                msg["Message-ID"] = make_msgid()
            to_send = msg.as_bytes()
        except Exception as e:  # message atypique : on l'envoie tel quel
            log.warning("Réécriture de l'expéditeur impossible (%s) : envoi tel quel", e)
    with _connect(up) as s:
        refused = s.sendmail(envelope_from, rcpts, to_send)
    if refused:
        log.warning("Destinataires refusés par le serveur : %s", refused)


def send_test(up: dict, to_addr: str) -> None:
    msg = EmailMessage()
    sender = (up.get("from_addr") or up.get("username")).strip()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = "Test Toshiba & Lexmark Scan Setup"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(
        "Ce message confirme que les paramètres SMTP fonctionnent.\n\n"
        f"Serveur : {up['host']}:{up['port']} ({SECURITY_LABELS.get(up.get('security'), '')})\n"
        f"Envoyé le {datetime.now():%d/%m/%Y à %H:%M:%S}\n"
    )
    with _connect(up) as s:
        s.send_message(msg, from_addr=sender, to_addrs=[to_addr])


_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _safe_name(name: str) -> str:
    name = _BAD_CHARS.sub("_", name).strip(" .")
    return name[:150] or "scan"


def save_attachments(raw: bytes, relay: dict) -> list:
    """Enregistre les pièces jointes (PDF, JPEG, TIFF...) du message dans le dossier configuré."""
    folder = Path(relay.get("save_folder") or config.default_scan_folder())
    if relay.get("subfolder_by_date", True):
        folder = folder / datetime.now().strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    saved = []
    stamp = datetime.now().strftime("%H%M%S")
    for part in msg.walk():
        if part.is_multipart():
            continue
        fname = part.get_filename()
        ctype = part.get_content_type()
        if not fname:
            if ctype.startswith("text/") or ctype.startswith("message/"):
                continue  # corps du message
            ext = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/tiff": ".tif"}.get(ctype, ".bin")
            fname = "scan" + ext
        data = part.get_payload(decode=True)
        if not data:
            continue
        target = folder / f"{stamp}_{_safe_name(fname)}"
        n = 1
        while target.exists():
            target = folder / f"{stamp}_{n}_{_safe_name(fname)}"
            n += 1
        target.write_bytes(data)
        saved.append(target)
    return saved


# ---------------------------------------------------------------- file d'attente
def enqueue(mail_from: str, rcpts: list, raw: bytes) -> Path:
    qid = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    d = config.queue_dir()
    (d / f"{qid}.eml").write_bytes(raw)
    (d / f"{qid}.json").write_text(json.dumps({"from": mail_from, "rcpts": rcpts, "tries": 0}), encoding="utf-8")
    return d / f"{qid}.eml"


def process_queue(cfg: dict) -> int:
    """Retente l'envoi des messages en attente. Retourne le nombre envoyé."""
    sent = 0
    for meta_path in sorted(config.queue_dir().glob("*.json")):
        eml = meta_path.with_suffix(".eml")
        if not eml.exists():
            meta_path.unlink(missing_ok=True)
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        try:
            send_upstream(cfg["upstream"], cfg["relay"], meta["from"], meta["rcpts"], eml.read_bytes())
        except Exception as e:
            meta["tries"] = meta.get("tries", 0) + 1
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            log.warning("File d'attente : nouvel échec pour %s (%s)", eml.name, e)
            if meta["tries"] >= 288:  # ~24 h de tentatives toutes les 5 min
                eml.rename(eml.with_suffix(".failed"))
                meta_path.unlink(missing_ok=True)
                log.error("Abandon de %s après 24 h d'échecs", eml.name)
            continue
        eml.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        sent += 1
        log.info("File d'attente : message %s envoyé à %s", eml.name, ", ".join(meta["rcpts"]))
    return sent


def queue_size() -> int:
    return len(list(config.queue_dir().glob("*.eml")))
