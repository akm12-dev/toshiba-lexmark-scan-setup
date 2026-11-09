# Toshiba & Lexmark Scan Setup

Utilitaire **AKM12** qui configure le **scan vers dossier (SMB)** et le **scan vers e-mail (SMTP)**
des multifonctions **Toshiba e-STUDIO** (TopAccess) et **Lexmark** (Embedded Web Server) compatibles.

Fiche officielle et téléchargements : https://akm12.com/logiciels/toshiba-lexmark-scan-setup

## Fonctionnalités

- Création du dossier partagé SMB, du compte local « scanner » et de la règle de pare-feu (Windows et macOS).
- Relais SMTP local : reçoit les scans de l'imprimante et les transmet au fournisseur de messagerie (TLS),
  avec file d'attente en cas d'échec.
- Préréglages : Gmail, Outlook, Microsoft 365, OVH, IONOS, Infomaniak, Orange, Free, SFR, Yahoo, iCloud.
- Choix de la marque et fiche des réglages TopAccess ou Embedded Web Server à copier ou exporter.
- Cohabitation avec Canon Scan Setup : configurations séparées ; un seul relais peut écouter sur le port 25 (utiliser 2525 pour l'autre).
- Journal des opérations et démarrage automatique du relais.

## Prérequis

- Python 3.9 ou plus récent ([python.org](https://www.python.org/downloads/)). Aucune autre dépendance.
- Droits administrateur pour créer le partage et le compte local.

## Démarrer depuis le code source

```bash
git clone <adresse du dépôt>
cd toshiba-lexmark-scan-setup
```

- **Windows** : double-cliquer sur `Lancer_Windows.bat`
- **macOS** : clic droit sur `Lancer_Mac.command` › Ouvrir
- Ligne de commande : `python ToshibaLexmarkScanSetup.py`
- Relais SMTP sans interface : `python ToshibaLexmarkScanSetup.py --relay`

Pour une utilisation en intervention, préférez la version officielle publiée dans les
[Releases](../../releases) du dépôt.

## Créer un exécutable (facultatif)

Nécessite PyInstaller (`pip install pyinstaller`).

- Windows : `build_windows.bat` → `dist\ToshibaLexmarkScanSetup.exe`
- macOS : `bash build_mac.sh` → `dist/ToshibaLexmarkScanSetup.app`

## Structure

```
ToshibaLexmarkScanSetup.py          point d'entrée
tlscan/
  gui.py                   interface graphique (tkinter)
  sharing.py               création du partage SMB (Windows / macOS)
  smtp_relay.py            relais SMTP local
  mailer.py                envoi vers le fournisseur, pièces jointes, file d'attente
  autostart.py             démarrage automatique, pare-feu
  printer_summary.py       fiche des réglages TopAccess / EWS
  config.py, netutil.py    configuration, outils réseau
docs/
  Guide_Toshiba_Lexmark_Scan_Setup.pdf  guide utilisateur illustré
  build/                       fabrication du guide et tests (voir ci-dessous)
```

## Configuration et sécurité

La configuration est enregistrée dans `%APPDATA%\ToshibaLexmarkScanSetup\` (Windows) ou
`~/Library/Application Support/ToshibaLexmarkScanSetup/` (macOS). Le fichier `config.json` contient les
mots de passe : il ne doit **jamais** être partagé ni ajouté à un dépôt Git (il est exclu par `.gitignore`).
Retirez toute information sensible des journaux avant de les transmettre.

## Tests et documentation

Depuis `docs/build/` :

- `py test_relay.py` : test de bout en bout du relais SMTP (authentification, transfert, pièces jointes, file d'attente).
- `py check_scripts.py <dossier>` : génère les scripts de partage SMB pour contrôle.
- `powershell -ExecutionPolicy Bypass -File build_guide.ps1` : régénère `docs/Guide_Toshiba_Lexmark_Scan_Setup.pdf`
  (nécessite ReportLab).

## Contribuer

Les signalements et propositions sont bienvenus via les Issues. Les modifications passent par une
Pull Request, relue et validée avant intégration : la branche `main` et les versions officielles sont
gérées uniquement par AKM12.

## Licence

Licence en cours de définition. En l'absence de fichier `LICENSE`, **tous droits réservés** :
le code peut être consulté, mais pas réutilisé ni redistribué sans autorisation.

---

AKM12 — Advanced Knowledge & Maintenance · https://akm12.com
