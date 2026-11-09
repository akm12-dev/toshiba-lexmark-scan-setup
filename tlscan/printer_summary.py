"""Génère la fiche des réglages à saisir dans l'interface Web de l'imprimante
(Toshiba : TopAccess — Lexmark : Embedded Web Server)."""
from datetime import datetime

from . import BRANDS, netutil
from .mailer import SECURITY_LABELS

WEB_UI = {"toshiba": "TopAccess", "lexmark": "Embedded Web Server (EWS)"}


def _tls_value(brand: str, security: str) -> str:
    if brand == "toshiba":
        return {"starttls": "STARTTLS", "ssl": "Over SSL (SSL/TLS)", "none": "Désactivé"}[security]
    return {"starttls": "Négocier (Negotiate)", "ssl": "Requis (Required)", "none": "Désactivé (Disabled)"}[security]


def build(cfg: dict) -> str:
    brand = cfg.get("brand", "toshiba")
    ip = netutil.local_ip()
    host = netutil.hostname()
    s, up, rl = cfg["share"], cfg["upstream"], cfg["relay"]
    unc = f"\\\\{ip}\\{s['share_name']}"
    pwd_share = s["password"] or "(celui défini dans le logiciel)"
    L = []
    add = L.append
    add(f"FICHE DE RÉGLAGES — {BRANDS[brand].upper()}")
    add(f"Générée le {datetime.now():%d/%m/%Y à %H:%M} — PC : {host} ({ip})")
    if cfg.get("printer_ip"):
        add(f"Interface Web ({WEB_UI[brand]}) : http://{cfg['printer_ip']}  (connexion administrateur)")
    add("")

    # ------------------------------------------------------------ 1. dossier
    add("════════ 1. SCAN VERS DOSSIER (SMB) ════════")
    if brand == "toshiba":
        add("TopAccess › Administration › Configuration › Enregistrer en tant que fichier")
        add("   (Setup › Save as file) › Destination « Remote 1 » (ou Remote 2)")
        add("   › « Utiliser le dossier réseau suivant »")
        add("")
        add("  Protocole ............ SMB")
        add(f"  Nom du serveur ....... {ip}")
        add(f"  Chemin réseau ........ {unc}")
        add(f"  Nom d'utilisateur .... {s['username']}")
        add(f"  Mot de passe ......... {pwd_share}")
        add("")
        add("  Sur le panneau : Numériser › Fichier › Remote 1  (ou créez un modèle :")
        add("  TopAccess › Enregistrement › Modèles › groupe Public › Enregistrer en tant que fichier)")
    else:
        add("EWS › Applications › Numériser vers réseau (Scan to Network) › Créer une destination")
        add("   (anciens modèles : Paramètres › Raccourcis › Dossier réseau)")
        add("")
        add("  Nom affiché .......... Scans PC (au choix)")
        add("  Type de dossier ...... SMB")
        add(f"  Chemin du dossier .... {unc}")
        add("  Authentification ..... Utiliser le nom d'utilisateur et le mot de passe attribués")
        add(f"  Nom d'utilisateur .... {s['username']}")
        add(f"  Mot de passe ......... {pwd_share}")
        add("  Domaine .............. (vide)")
        add("")
        add("  Sur le panneau : Numériser vers réseau › Scans PC")
    add("")
    add(f"  Si refus : essayer Nom d'utilisateur = {host}\\{s['username']}")
    add(f"  Les fichiers arrivent dans : {s['folder']}")
    add("  Conseil : fixez l'IP du PC (réservation DHCP dans la box) pour que l'adresse ne change pas.")
    add("")

    # ------------------------------------------------------------ 2. e-mail
    add("════════ 2. SCAN VERS E-MAIL (SMTP) ════════")
    if brand == "toshiba":
        add("TopAccess › Administration › Configuration › Réseau › Client SMTP (SMTP Client)")
        add("   + Administration › Configuration › E-mail : Adresse d'expéditeur (From Address)")
    else:
        add("EWS › Paramètres › E-mail › Configuration de l'e-mail (E-mail Setup)")
        add("   (anciens modèles : Paramètres › Réseau/Ports › Configuration SMTP)")
    add("")
    sender = up.get("from_addr") or up.get("username") or "scanner@votre-domaine.fr"
    if rl.get("mode") == "relay":
        add("Mode : RELAIS VIA CE PC (le PC doit être allumé et le relais démarré)")
        add("")
        server, port, tls = ip, rl["listen_port"], _tls_value(brand, "none")
        auth_on = bool(rl.get("auth_user"))
        auth_user, auth_pwd = rl.get("auth_user", ""), rl.get("auth_password", "")
    else:
        add("Mode : DIRECT (l'imprimante contacte directement le fournisseur)")
        add("")
        server, port, tls = up["host"], up["port"], _tls_value(brand, up["security"])
        auth_on, auth_user, auth_pwd = True, up["username"], "(mot de passe d'application du compte)"

    if brand == "toshiba":
        add("  Activer client SMTP .. Activé")
        add(f"  Adresse serveur SMTP . {server}")
        add(f"  Numéro de port ....... {port}")
        add(f"  SSL/TLS .............. {tls}")
        if auth_on:
            add("  Authentification ..... LOGIN (ou Auto)")
            add(f"    Nom de connexion ... {auth_user}")
            add(f"    Mot de passe ....... {auth_pwd}")
        else:
            add("  Authentification ..... Désactivé")
        add("  POP avant SMTP ....... Désactivé")
        add(f"  Adresse d'expéditeur . {sender}   (menu E-mail)")
    else:
        add(f"  Passerelle SMTP princ. {server}")
        add(f"  Port passerelle ...... {port}")
        add(f"  Utiliser SSL/TLS ..... {tls}")
        add(f"  Exiger certificat .... {'Non' if rl.get('mode') == 'relay' else 'Oui si firmware à jour, sinon Non'}")
        add(f"  Adresse de réponse ... {sender}")
        if auth_on:
            add("  Authentification serveur SMTP : Login / Plain")
            add("  E-mail initié par le périphérique : Utiliser les identifiants SMTP du périphérique")
            add(f"    ID utilisateur ..... {auth_user}")
            add(f"    Mot de passe ....... {auth_pwd}")
        else:
            add("  Authentification serveur SMTP : Aucune authentification requise")
            add("  E-mail initié par le périphérique : Aucun")
    add("")
    if rl.get("mode") == "relay":
        add(f"  Le PC retransmet ensuite via {up['host'] or '(fournisseur à configurer)'}:{up['port']} "
            f"({SECURITY_LABELS.get(up['security'], '')})")
        if int(rl["listen_port"]) != 25:
            add("  Si le port n'est pas réglable sur l'imprimante, utilisez 25 dans le logiciel.")
        if rl.get("save_attachments"):
            add(f"  Les pièces jointes sont aussi copiées dans : {rl['save_folder']}")
    else:
        add("  ⚠ Les modèles anciens ne gèrent pas toujours TLS 1.2/1.3 ni les mots de passe")
        add("    d'application : en cas d'échec, passez en mode « Relais via ce PC ».")
    add("")

    # ------------------------------------------------------------ 3. diagnostic
    add("════════ 3. OÙ LIRE LES ERREURS SUR L'IMPRIMANTE ════════")
    if brand == "toshiba":
        add("  TopAccess › Journaux › Journal de numérisation / Journal d'envoi : code et cause de l'échec")
        add("  TopAccess › Administration › Configuration › Réseau › SMB : versions SMB autorisées")
        add("  Panneau › État des travaux › Journal › Numérisation")
    else:
        add("  EWS › Rapports › Périphérique / Réseau : état SMTP et SMB")
        add("  EWS › Applications › Numériser vers réseau › Tester la connexion (si proposé)")
        add("  EWS › Paramètres › E-mail › bouton « Tester la connexion » (firmwares récents)")
    add("  Messages typiques : serveur introuvable (IP/DNS), connexion refusée ou délai dépassé")
    add("  (pare-feu, relais arrêté, port), échec d'authentification (identifiant / mot de passe).")
    add("  Les intitulés exacts des menus varient selon le modèle et la version du micrologiciel.")
    return "\n".join(L)
