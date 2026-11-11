import sys
from pathlib import Path
import types as _t
_pil = _t.ModuleType('PIL'); _img = _t.ModuleType('PIL.Image'); _pil.Image = _img
sys.modules['PIL'] = _pil; sys.modules['PIL.Image'] = _img  # Pillow bloque par Windows : JPEG gere nativement
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, KeepTogether, NextPageTemplate, Flowable, CondPageBreak)

SHOTS = Path(sys.argv[1])
OUT = Path(sys.argv[2])
F = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("UI", F + r"\segoeui.ttf"))
pdfmetrics.registerFont(TTFont("UI-B", F + r"\segoeuib.ttf"))
pdfmetrics.registerFont(TTFont("UI-I", F + r"\segoeuii.ttf"))
pdfmetrics.registerFont(TTFont("UI-SB", F + r"\seguisb.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + r"\consola.ttf"))
pdfmetrics.registerFont(TTFont("Sym", F + r"\seguisym.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("UI", normal="UI", bold="UI-B", italic="UI-I", boldItalic="UI-B")

RED = colors.HexColor("#0B5C7A")  # accent (nom historique)
INK = colors.HexColor("#1F2328")
MUTED = colors.HexColor("#59636E")
LINE = colors.HexColor("#D0D7DE")
SOFT = colors.HexColor("#F6F8FA")
TIP_BG = colors.HexColor("#EEF6FF"); TIP_BD = colors.HexColor("#4A8FE0")
WARN_BG = colors.HexColor("#FFF5E6"); WARN_BD = colors.HexColor("#E59400")

ss = {}
ss["body"] = ParagraphStyle("body", fontName="UI", fontSize=10, leading=14.5, textColor=INK, spaceAfter=6)
ss["h1"] = ParagraphStyle("h1", fontName="UI-B", fontSize=20, leading=25, textColor=INK, spaceBefore=4, spaceAfter=4)
ss["kicker"] = ParagraphStyle("kicker", fontName="UI-SB", fontSize=9.5, leading=12, textColor=RED, spaceAfter=2)
ss["h2"] = ParagraphStyle("h2", fontName="UI-B", fontSize=13, leading=17, textColor=INK, spaceBefore=12, spaceAfter=5)
ss["h3"] = ParagraphStyle("h3", fontName="UI-SB", fontSize=11, leading=15, textColor=INK, spaceBefore=8, spaceAfter=3)
ss["small"] = ParagraphStyle("small", parent=ss["body"], fontSize=8.5, leading=11.5, textColor=MUTED)
ss["cap"] = ParagraphStyle("cap", parent=ss["small"], alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)
ss["cell"] = ParagraphStyle("cell", fontName="UI", fontSize=9, leading=12, textColor=INK)
ss["cellb"] = ParagraphStyle("cellb", parent=ss["cell"], fontName="UI-SB")
ss["cellh"] = ParagraphStyle("cellh", parent=ss["cell"], fontName="UI-B", textColor=colors.white)
ss["mono"] = ParagraphStyle("mono", fontName="Mono", fontSize=8.8, leading=12, textColor=INK)
ss["step"] = ParagraphStyle("step", parent=ss["body"], leftIndent=22, firstLineIndent=0, spaceAfter=4)

P = lambda t, s="body": Paragraph(t, ss[s])
W = A4[0] - 4.4 * cm


def chk():
    return '<font name="Sym">\u2714</font>'


def box(title, text, kind="tip"):
    bg, bd = (TIP_BG, TIP_BD) if kind == "tip" else (WARN_BG, WARN_BD)
    label = {"tip": "Conseil", "warn": "Attention", "info": "À savoir"}.get(kind, kind)
    content = [Paragraph(f"<b>{title or label}</b>", ss["cellb"]), Spacer(1, 2)]
    for t in ([text] if isinstance(text, str) else text):
        content.append(Paragraph(t, ss["cell"]))
    t = Table([[content]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, bd),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 8)])


def table(rows, widths, header=True):
    data = []
    for i, r in enumerate(rows):
        st = "cellh" if header and i == 0 else "cell"
        data.append([Paragraph(str(c), ss[st if not (j == 0 and i > 0) else "cellb"]) for j, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), INK))
    for i in range(1 if header else 0, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    t.setStyle(TableStyle(style))
    return t


def code(lines):
    t = Table([[Paragraph(l.replace(" ", "&nbsp;") or "&nbsp;", ss["mono"])] for l in lines], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                           ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, -1), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 8)])


def shot(name, caption, width=14.5 * cm):
    p = SHOTS / name
    img = Image(str(p))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width, width * ratio
    frame = Table([[img]], colWidths=[width + 2])
    frame.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 1),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return KeepTogether([frame, P(caption, "cap")])


def steps(items):
    out = []
    for i, t in enumerate(items, 1):
        num = Table([[Paragraph(f'<font color="white"><b>{i}</b></font>', ParagraphStyle(
            "n", fontName="UI-B", fontSize=9, leading=11, alignment=TA_CENTER))]], colWidths=[0.55 * cm],
            rowHeights=[0.55 * cm])
        num.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), RED), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("ROUNDEDCORNERS", [8, 8, 8, 8]), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        row = Table([[num, Paragraph(t, ss["body"])]], colWidths=[0.85 * cm, W - 0.85 * cm])
        row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        out.append(row)
    return out


class Diagram(Flowable):
    """Schéma de flux : liste de nœuds reliés par des flèches étiquetées."""

    def __init__(self, nodes, labels, height=2.6 * cm, note=None):
        super().__init__()
        self.nodes, self.labels, self.h, self.note = nodes, labels, height, note
        self.width = W

    def wrap(self, aw, ah):
        return W, self.h

    def draw(self):
        c = self.canv
        n = len(self.nodes)
        gap = 2.6 * cm
        bw = (W - gap * (n - 1)) / n
        bh = 1.6 * cm
        y = (self.h - bh) / 2 + 0.1 * cm
        for i, (title, sub, accent) in enumerate(self.nodes):
            x = i * (bw + gap)
            c.setFillColor(RED if accent else SOFT)
            c.setStrokeColor(RED if accent else LINE)
            c.roundRect(x, y, bw, bh, 6, fill=1, stroke=1)
            c.setFillColor(colors.white if accent else INK)
            c.setFont("UI-B", 10)
            c.drawCentredString(x + bw / 2, y + bh - 0.62 * cm, title)
            c.setFont("UI", 8)
            c.setFillColor(colors.HexColor("#D6EEF7") if accent else MUTED)
            for k, line in enumerate(sub.split("\n")):
                c.drawCentredString(x + bw / 2, y + bh - 1.05 * cm - k * 0.34 * cm, line)
            if i < n - 1:
                x1, x2, ym = x + bw + 0.12 * cm, x + bw + gap - 0.12 * cm, y + bh / 2
                c.setStrokeColor(INK); c.setLineWidth(1.3)
                c.line(x1, ym, x2 - 0.15 * cm, ym)
                p = c.beginPath(); p.moveTo(x2, ym); p.lineTo(x2 - 0.22 * cm, ym + 0.12 * cm)
                p.lineTo(x2 - 0.22 * cm, ym - 0.12 * cm); p.close()
                c.setFillColor(INK); c.drawPath(p, fill=1, stroke=0)
                c.setFont("UI-SB", 7.5); c.setFillColor(MUTED)
                for k, line in enumerate(self.labels[i].split("\n")):
                    c.drawCentredString((x1 + x2) / 2, ym + 0.22 * cm + (len(self.labels[i].split("\n")) - 1 - k) * 0.3 * cm, line)


# ------------------------------------------------------------------ pages
def on_cover(c, doc):
    w, h = A4
    c.setFillColor(RED); c.rect(0, h - 11 * cm, w, 11 * cm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("UI-SB", 12); c.drawString(2.2 * cm, h - 3 * cm, "GUIDE D'UTILISATION")
    c.setFont("UI-B", 30); c.drawString(2.2 * cm, h - 4.8 * cm, "Toshiba & Lexmark Scan Setup")
    c.setFont("UI", 15)
    c.drawString(2.2 * cm, h - 6.0 * cm, "Scan vers dossier et Scan vers e-mail")
    c.drawString(2.2 * cm, h - 6.75 * cm, "pour multifonctions Toshiba e-STUDIO et Lexmark — PC Windows et Mac")
    c.setFont("UI", 10); c.setFillColor(colors.HexColor("#D6EEF7"))
    c.drawString(2.2 * cm, h - 9.6 * cm, "Version 1.1  •  Novembre 2026")
    c.setFillColor(MUTED); c.setFont("UI", 8.5)
    c.drawString(2.2 * cm, 1.8 * cm, "Toshiba et e-STUDIO sont des marques de Toshiba Tec Corporation ; "
                                     "Lexmark est une marque de Lexmark International, Inc.")
    c.drawString(2.2 * cm, 1.4 * cm, "Ce logiciel est indépendant et n'est édité ni par Toshiba ni par Lexmark.")


def on_page(c, doc):
    w, h = A4
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.line(2.2 * cm, h - 1.5 * cm, w - 2.2 * cm, h - 1.5 * cm)
    c.setFont("UI", 8); c.setFillColor(MUTED)
    c.drawString(2.2 * cm, h - 1.25 * cm, "Toshiba & Lexmark Scan Setup — Guide d'utilisation")
    c.drawRightString(w - 2.2 * cm, 1.2 * cm, f"{doc.page}")
    c.setFillColor(RED); c.rect(2.2 * cm, h - 1.52 * cm, 1.2 * cm, 0.06 * cm, fill=1, stroke=0)


doc = BaseDocTemplate(str(OUT), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2.1 * cm,
                      bottomMargin=1.9 * cm, title="Toshiba & Lexmark Scan Setup — Guide d'utilisation",
                      author="Toshiba & Lexmark Scan Setup", subject="Scan vers dossier et scan vers e-mail pour multifonctions Toshiba et Lexmark")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
cover_frame = Frame(doc.leftMargin, doc.bottomMargin + 1.5 * cm, doc.width, A4[1] - 13.5 * cm - doc.bottomMargin, id="c")
doc.addPageTemplates([PageTemplate("cover", [cover_frame], onPage=on_cover),
                      PageTemplate("main", [frame], onPage=on_page)])

S = []
add = S.append

# ------------------------------------------------------------------ couverture : sommaire
add(NextPageTemplate("main"))
add(P("Ce que fait le logiciel", "h2"))
add(P("Toshiba &amp; Lexmark Scan Setup prépare un ordinateur Windows ou Mac pour recevoir les documents "
      "numérisés par un multifonction Toshiba e-STUDIO ou Lexmark, sans manipulation technique : il crée le dossier partagé, "
      "le compte d'accès et les règles de pare-feu, teste votre messagerie, sert de relais e-mail si "
      "l'imprimante est trop ancienne pour les serveurs actuels, puis vous donne la liste exacte des "
      "valeurs à saisir sur l'imprimante."))
add(Spacer(1, 6))
toc = [["Section", "Contenu", "Page"],
       ["1", "Principe et prérequis", "2"],
       ["2", "Installation (Windows et Mac)", "4"],
       ["3", "Premier lancement — page Accueil", "6"],
       ["4", "Scan vers dossier (SMB)", "7"],
       ["5", "Scan vers e-mail (SMTP direct ou relais)", "10"],
       ["6", "Réglages à saisir sur l'imprimante", "15"],
       ["7", "Toshiba : dossier FILE_SHARE du copieur", "16"],
       ["8", "Dépannage", "17"],
       ["9", "Sécurité, maintenance et désinstallation", "19"]]
add(table(toc, [2 * cm, W - 4 * cm, 2 * cm]))
add(PageBreak())

# ------------------------------------------------------------------ 1. Principe
add(P("SECTION 1", "kicker")); add(P("Principe et prérequis", "h1"))
add(P("Un multifonction Toshiba ou Lexmark peut envoyer une numérisation de deux façons. Le logiciel gère les deux, "
      "et vous pouvez utiliser l'une, l'autre ou les deux à la fois."))
add(P("Scan vers dossier", "h2"))
add(P("L'imprimante dépose le fichier (PDF, JPEG, TIFF) directement dans un dossier partagé de l'ordinateur, "
      "via le protocole de partage de fichiers Windows (SMB). Les Mac utilisent le même protocole."))
add(Diagram([("Multifonction", "Numériser > Fichier\nou Réseau", False),
             ("Ce PC / Mac", "partage \\\\IP\\SCANS\ncompte « scanner »", True),
             ("Dossier", "C:\\Scans  ou\n/Users/Shared/Scans", False)],
            ["SMB (port 445)", "enregistrement"]))
add(P("Scan vers e-mail", "h2"))
add(P("L'imprimante envoie un e-mail avec le document en pièce jointe. Elle a besoin d'un serveur d'envoi "
      "(SMTP). Deux modes sont proposés :"))
add(P("<b>Mode direct</b> — l'imprimante contacte elle-même le serveur du fournisseur (Gmail, OVH…). "
      "Simple, mais beaucoup de multifonctions de plus de 5 à 8 ans ne gèrent pas le chiffrement exigé "
      "aujourd'hui (TLS 1.2/1.3) ni les mots de passe d'application."))
add(Diagram([("Multifonction", "TLS + identifiants", False),
             ("Fournisseur", "smtp.gmail.com…", False),
             ("Destinataire", "boîte de réception", False)],
            ["SMTP 587 / 465", "e-mail"], height=2.3 * cm))
add(P("<b>Mode relais via ce PC (recommandé)</b> — l'imprimante envoie à l'ordinateur sur le réseau local, "
      "sans chiffrement. Le logiciel retransmet ensuite au fournisseur avec un chiffrement moderne. "
      "Il peut en plus enregistrer les pièces jointes dans un dossier."))
add(Diagram([("Multifonction", "aucun réglage\nde sécurité", False),
             ("Relais (ce PC)", "Scan Setup\nport 25", True),
             ("Fournisseur", "TLS + mot de passe\nd'application", False)],
            ["SMTP local\nsans TLS", "SMTP 587 / 465\nchiffré"], height=2.6 * cm))
add(box("Le relais ne fonctionne que si l'ordinateur est allumé",
        "En mode relais, le PC ou le Mac doit être allumé, session ouverte, avec le relais démarré "
        "(automatiquement de préférence, voir section 5.5). Choisissez un poste qui reste allumé "
        "pendant les heures de bureau.", "warn"))
add(P("Prérequis", "h2"))
add(table([["Élément", "Détail"],
           ["Ordinateur", "Windows 10 ou 11 (y compris édition Famille), ou macOS 11 Big Sur et plus récent."],
           ["Python", "Python 3.9 ou plus récent, gratuit (python.org). Aucun autre module à installer."],
           ["Droits", "Un compte administrateur de l'ordinateur (demandé uniquement pour créer le partage "
                      "et ouvrir le pare-feu)."],
           ["Réseau", "L'imprimante et l'ordinateur sur le même réseau local (même box / même routeur)."],
           ["Imprimante", "Toshiba e-STUDIO avec interface Web TopAccess, ou Lexmark (CX, MX, XC, XM, MB, MC, "
                          "MS…) proposant la numérisation vers un dossier réseau et/ou vers e-mail."],
           ["Accès imprimante", "L'adresse IP du multifonction et le mot de passe administrateur de son "
                                "interface Web : TopAccess chez Toshiba (sur de nombreux modèles, compte admin, "
                                "mot de passe d'usine souvent 123456 à changer) ; Embedded Web Server (EWS) chez "
                                "Lexmark (mot de passe défini par l'administrateur, parfois aucun)."],
           ["Messagerie", "Pour le scan vers e-mail : un compte e-mail et, pour Gmail/Yahoo/iCloud, "
                          "un mot de passe d'application."]], [3.3 * cm, W - 3.3 * cm]))
add(PageBreak())

# ------------------------------------------------------------------ 2. Installation
add(P("SECTION 2", "kicker")); add(P("Installation", "h1"))
add(P("Le logiciel est livré sous forme de dossier <b>ToshibaLexmarkScanSetup</b>. Copiez ce dossier sur l'ordinateur "
      "qui recevra les numérisations, par exemple dans Documents."))
add(table([["Fichier", "Rôle"],
           ["Lancer_Windows.bat", "Démarre le logiciel sous Windows (double-clic)."],
           ["Lancer_Mac.command", "Démarre le logiciel sous macOS (clic droit > Ouvrir)."],
           ["ToshibaLexmarkScanSetup.py", "Programme principal (peut aussi être lancé en ligne de commande)."],
           ["tlscan/", "Modules du logiciel : interface, partage, relais SMTP…"],
           ["build_windows.bat / build_mac.sh", "Facultatif : crée un exécutable autonome (.exe / .app)."],
           ["LISEZMOI.txt", "Résumé rapide."]], [5.2 * cm, W - 5.2 * cm]))
add(P("2.1 Sous Windows", "h2"))
for s in steps([
    "Installez Python depuis <b>python.org/downloads</b>. Pendant l'installation, cochez "
    "<b>« Add python.exe to PATH »</b>.",
    "Ouvrez le dossier ToshibaLexmarkScanSetup et double-cliquez sur <b>Lancer_Windows.bat</b>.",
    "Si Windows affiche « Windows a protégé votre ordinateur », cliquez sur <b>Informations "
    "complémentaires</b> puis <b>Exécuter quand même</b>."]):
    add(s)
add(P("2.2 Sous macOS", "h2"))
for s in steps([
    "Installez Python depuis <b>python.org/downloads/macos</b> (la version d'Apple fournie avec les outils "
    "de développement fonctionne aussi, mais son interface est moins soignée).",
    "Faites un <b>clic droit</b> sur <b>Lancer_Mac.command</b> > <b>Ouvrir</b>, puis confirmez. "
    "Les fois suivantes, un double-clic suffit.",
    "Si macOS indique que le fichier n'est pas exécutable, ouvrez le Terminal, tapez <font name='Mono'>chmod +x </font>"
    "suivi d'un espace, glissez le fichier dans la fenêtre, puis appuyez sur Entrée.",
    "Au premier démarrage du relais e-mail, macOS demande <b>« Autoriser les connexions entrantes ? »</b> : "
    "cliquez sur <b>Autoriser</b>."]):
    add(s)
add(P("2.3 Exécutable autonome (facultatif)", "h2"))
add(P("Pour installer le logiciel sur d'autres postes sans Python, créez un exécutable une fois sur un poste "
      "équipé de Python : <b>build_windows.bat</b> produit <font name='Mono'>dist\\ToshibaLexmarkScanSetup.exe</font>, "
      "<b>build_mac.sh</b> produit <font name='Mono'>dist/ToshibaLexmarkScanSetup.app</font>. Ces fichiers ne sont pas "
      "signés : Windows SmartScreen et macOS Gatekeeper afficheront un avertissement au premier lancement."))
add(box("Déjà équipé de Canon Scan Setup ?",
        ["Les deux logiciels peuvent être installés sur le même ordinateur : leurs configurations, journaux, "
         "démarrages automatiques et règles de pare-feu sont séparés. Ils peuvent partager le même dossier "
         "SCANS et le même compte « scanner ».",
         "En revanche, un seul relais SMTP peut écouter sur un port donné : si les deux relais doivent tourner "
         "en même temps, réglez l'un d'eux sur un autre port (ex. 2525) — Toshiba et Lexmark permettent tous "
         "deux de choisir le port SMTP."]))
add(PageBreak())

# ------------------------------------------------------------------ 3. Accueil
add(P("SECTION 3", "kicker")); add(P("Premier lancement — page Accueil", "h1"))
add(P("La barre de gauche donne accès, dans l'ordre, à chaque étape de la configuration ; le bouton "
      "<b>Enregistrer</b> en bas à droite sauvegarde les réglages. La page Accueil affiche le nom et l'adresse IP "
      "de l'ordinateur. <b>Notez cette adresse IP</b> : c'est elle que l'imprimante utilisera pour joindre "
      "l'ordinateur."))
add(shot("1_accueil.jpg", "Figure 1 — Page Accueil"))
for s in steps([
    "Choisissez la <b>marque</b> (Toshiba e-STUDIO ou Lexmark) : la fiche de réglages s'adapte aux menus "
    "de l'imprimante.",
    "Relevez l'<b>adresse IP de l'imprimante</b> : chez Lexmark, elle est affichée en haut de l'écran "
    "d'accueil ; chez Toshiba, imprimez la liste de configuration réseau depuis le panneau, ou demandez-la "
    "à votre installateur.",
    "Saisissez-la et cliquez sur <b>Tester la connexion</b>. Le message vert confirme que l'imprimante est "
    "joignable et que son interface Web est active.",
    "Le bouton <b>Ouvrir l'interface Web (TopAccess / EWS)</b> ouvre la page de configuration de "
    "l'imprimante dans votre navigateur. Vous en aurez besoin plus loin."]):
    add(s)
add(box("Fixez l'adresse IP de l'ordinateur",
        "Si la box attribue une nouvelle adresse IP à l'ordinateur, l'imprimante ne le trouvera plus. "
        "Dans l'interface de votre box (ou du routeur), créez une <b>réservation DHCP</b> (bail statique) "
        "pour l'ordinateur et, si possible, pour l'imprimante."))
add(PageBreak())

# ------------------------------------------------------------------ 4. Scan vers dossier
add(P("SECTION 4", "kicker")); add(P("Scan vers dossier (SMB)", "h1"))
add(P("4.1 Créer le partage dans le logiciel", "h2"))
add(shot("2_dossier.jpg", "Figure 2 — Page Scan vers dossier", width=13.5 * cm))
for s in steps([
    "<b>Dossier de réception</b> : là où arriveront les fichiers. Par défaut <font name='Mono'>C:\\Scans</font> "
    "(Windows) ou <font name='Mono'>/Users/Shared/Scans</font> (Mac). Le dossier est créé s'il n'existe pas.",
    "<b>Nom du partage</b> : nom réseau du dossier, sans espace (par défaut SCANS).",
    "<b>Compte utilisateur</b> et <b>Mot de passe</b> : un compte local dédié, utilisé uniquement par "
    "l'imprimante. Le bouton <b>Générer</b> propose un mot de passe solide. Évitez les guillemets et "
    "l'antislash, mal gérés par certaines imprimantes.",
    "Cochez les options utiles (voir tableau ci-dessous), puis cliquez sur <b>Créer le partage</b>.",
    "Acceptez la demande d'autorisation (fenêtre « Contrôle de compte d'utilisateur » sous Windows, "
    "mot de passe administrateur sous macOS). Le compte rendu s'affiche en bas de la fenêtre.",
    "Cliquez sur <b>Vérifier</b> : le logiciel contrôle que le port 445 est ouvert et que le partage répond."]):
    add(s)
add(CondPageBreak(7 * cm))
add(P("Options (Windows)", "h3"))
add(table([["Option", "Effet", "Quand l'utiliser"],
           ["Créer / mettre à jour le compte", "Crée le compte local dédié, mot de passe sans expiration, "
            "masqué de l'écran de connexion.", "Toujours (recommandé)."],
           ["Ouvrir le pare-feu", "Active la règle « Partage de fichiers et d'imprimantes » pour les "
            "réseaux privés.", "Toujours."],
           ["Profil « Privé »", "Passe le réseau actuel de Public à Privé. En profil Public, Windows bloque "
            "le partage.", "Si l'ordinateur est sur le réseau du bureau ou de la maison."],
           ["Ne pas exiger la signature SMB", "Désactive la signature SMB obligatoire introduite par "
            "Windows 11 24H2.", "Uniquement si l'imprimante refuse la connexion malgré des "
            "réglages corrects."],
           ["Activer SMB1", "Réactive l'ancien protocole SMB1 (redémarrage requis).", "Seulement pour les "
            "très anciens modèles ne gérant pas SMB2/3. Protocole obsolète : à éviter."]],
          [3.8 * cm, 6.6 * cm, W - 10.4 * cm]))
add(P("Ce que fait le logiciel sous macOS", "h3"))
add(P("Il crée un compte de partage masqué (sans accès à une session), active pour lui l'option "
      "« Partage Windows » (mot de passe au format SMB), donne au compte le droit d'écrire dans le dossier, "
      "déclare le partage et démarre le service de partage de fichiers. Vous pouvez le vérifier dans "
      "<b>Réglages Système > Général > Partage > Partage de fichiers</b> (le dossier apparaît dans la liste)."))
add(box("Comptes Microsoft et code PIN",
        "N'utilisez pas votre propre compte Windows pour l'imprimante : avec un compte Microsoft ou une "
        "connexion par code PIN, le mot de passe réseau est souvent différent de ce que vous tapez, ce qui "
        "provoque des refus. Le compte dédié créé par le logiciel évite ce problème."))
add(P("4.2 Déclarer le dossier sur l'imprimante", "h2"))
add(P("Ouvrez l'interface Web de l'imprimante (bouton <b>Ouvrir l'interface Web</b> du logiciel) et connectez-vous "
      "en administrateur. Les valeurs exactes à saisir figurent dans la page <b>Réglages imprimante</b> du "
      "logiciel. Les intitulés des menus varient selon le modèle et la version du micrologiciel."))
add(P("Toshiba e-STUDIO (TopAccess)", "h3"))
for s in steps([
    "TopAccess > <b>Administration</b> > <b>Configuration</b> (Setup) > <b>Enregistrer en tant que fichier</b> "
    "(Save as file).",
    "Dans la partie <b>Destination</b>, choisissez <b>Remote 1</b> (ou Remote 2) puis <b>Utiliser le dossier "
    "réseau suivant</b>.",
    "Renseignez : Protocole <b>SMB</b>, Nom du serveur <b>IP du PC</b>, Chemin réseau "
    "<font name='Mono'>\\\\192.168.1.25\\SCANS</font>, Nom d'utilisateur <b>scanner</b>, Mot de passe. Enregistrez.",
    "Sur le panneau : <b>Numériser</b> > <b>Fichier</b> > <b>Remote 1</b>. Pour un bouton à une touche, créez un "
    "modèle : TopAccess > <b>Enregistrement</b> > <b>Modèles</b> > groupe Public > Enregistrer en tant que fichier."]):
    add(s)
add(P("Lexmark (Embedded Web Server)", "h3"))
for s in steps([
    "EWS > <b>Applications</b> > <b>Numériser vers réseau</b> (Scan to Network) > <b>Créer</b> une destination. "
    "Sur les anciens modèles : <b>Paramètres</b> > <b>Raccourcis</b> (ou Gérer les raccourcis) > Dossier réseau.",
    "Renseignez : Nom affiché (ex. « Scans PC »), Type de dossier <b>SMB</b>, Chemin "
    "<font name='Mono'>\\\\192.168.1.25\\SCANS</font>.",
    "Authentification : <b>Utiliser le nom d'utilisateur et le mot de passe attribués</b>, puis <b>scanner</b> et "
    "son mot de passe. Laissez le domaine vide. Cliquez sur <b>Tester la connexion</b> si le bouton existe, "
    "puis enregistrez.",
    "Sur le panneau : icône <b>Numériser vers réseau</b> > <b>Scans PC</b>."]):
    add(s)
add(table([["Champ", "Toshiba (TopAccess)", "Lexmark (EWS)"],
           ["Protocole / type", "SMB", "SMB"],
           ["Serveur / chemin", "Nom du serveur : 192.168.1.25<br/>Chemin réseau : \\\\192.168.1.25\\SCANS",
            "Chemin du dossier : \\\\192.168.1.25\\SCANS"],
           ["Identifiant", "Nom d'utilisateur : scanner", "Nom d'utilisateur : scanner (domaine vide)"],
           ["Mot de passe", "celui défini dans le logiciel", "celui défini dans le logiciel"]],
          [3.4 * cm, (W - 3.4 * cm) / 2, (W - 3.4 * cm) / 2]))
add(Spacer(1, 6))
add(box("L'imprimante refuse l'identifiant ?",
        ["Essayez la forme <font name='Mono'>NOMDUPC\\scanner</font> dans le champ Nom d'utilisateur "
         "(le nom du PC figure dans la page Accueil), ou indiquez le nom du PC comme domaine (Lexmark).",
         "Vérifiez que le chemin commence bien par deux antislashs.",
         "Toshiba : dans TopAccess > Administration > Configuration > Réseau > <b>SMB</b>, vérifiez que les versions "
         "SMB 2/3 sont autorisées et le réglage de signature SMB du client (si ces options existent sur votre modèle)."]))
add(PageBreak())

# ------------------------------------------------------------------ 5. E-mail
add(P("SECTION 5", "kicker")); add(P("Scan vers e-mail (SMTP)", "h1"))
add(P("5.1 Choisir le mode", "h2"))
add(table([["", "Direct", "Relais via ce PC"],
           ["Principe", "L'imprimante parle au fournisseur.", "L'imprimante parle au PC, qui retransmet."],
           ["PC allumé nécessaire", "Non", "Oui"],
           ["Imprimantes anciennes", "Souvent incompatibles (TLS, mot de passe d'application)",
            "Compatibles : aucun chiffrement demandé à l'imprimante"],
           ["En cas de panne Internet", "Envoi en échec", "Messages mis en file d'attente et renvoyés "
                                                         "automatiquement (toutes les 5 min, pendant 24 h)"],
           ["Copie dans un dossier", "Non", "Possible (pièces jointes enregistrées)"]],
          [3.8 * cm, (W - 3.8 * cm) / 2, (W - 3.8 * cm) / 2]))
add(Spacer(1, 4))
add(P("En cas de doute, choisissez <b>Relais via ce PC</b>."))
add(P("5.2 Configurer le compte de messagerie", "h2"))
add(shot("3_email.jpg", "Figure 3 — Page Scan vers e-mail, compte de messagerie", width=13.5 * cm))
for s in steps([
    "Choisissez votre <b>Fournisseur</b> : le serveur, le port et la sécurité se remplissent "
    "automatiquement. Une remarque propre au fournisseur s'affiche sous les champs.",
    "<b>Identifiant</b> : en général l'adresse e-mail complète. <b>Mot de passe</b> : pour Gmail, Yahoo "
    "et iCloud, un <b>mot de passe d'application</b> (voir 5.3), jamais le mot de passe habituel.",
    "<b>Adresse d'expédition</b> : l'adresse qui apparaîtra comme expéditeur. Laissez vide pour utiliser "
    "l'identifiant.",
    "Indiquez une adresse dans <b>Envoyer un test à</b> et cliquez sur <b>Tester l'envoi</b>. Un message "
    "vert confirme l'envoi ; vérifiez la réception (et le dossier Indésirables)."]):
    add(s)
add(P("Paramètres des principaux fournisseurs", "h3"))
add(table([["Fournisseur", "Serveur", "Port / sécurité", "Mot de passe"],
           ["Gmail / Google Workspace", "smtp.gmail.com", "587 STARTTLS", "Mot de passe d'application"],
           ["OVH", "ssl0.ovh.net", "465 SSL/TLS", "Mot de passe de la boîte"],
           ["IONOS", "smtp.ionos.fr", "465 SSL/TLS", "Mot de passe de la boîte"],
           ["Infomaniak", "mail.infomaniak.com", "465 SSL/TLS", "Mot de passe de la boîte"],
           ["Orange", "smtp.orange.fr", "465 SSL/TLS", "Mot de passe Orange"],
           ["Free", "smtp.free.fr", "465 SSL/TLS", "Mot de passe Free"],
           ["SFR", "smtp.sfr.fr", "465 SSL/TLS", "Mot de passe SFR"],
           ["Yahoo", "smtp.mail.yahoo.com", "465 SSL/TLS", "Mot de passe d'application"],
           ["iCloud", "smtp.mail.me.com", "587 STARTTLS", "Mot de passe pour app"],
           ["Outlook.com / Microsoft 365", "smtp-mail.outlook.com /\nsmtp.office365.com", "587 STARTTLS",
            "Voir l'encadré ci-dessous"]], [4.2 * cm, 4.4 * cm, 3 * cm, W - 11.6 * cm]))
add(box("Outlook.com, Hotmail et Microsoft 365", [
    "Microsoft supprime progressivement l'authentification SMTP par simple mot de passe au profit d'OAuth "
    "(connexion moderne), que les imprimantes et ce logiciel ne gèrent pas. Si le test d'envoi est refusé "
    "(erreur 535 ou « basic authentication is disabled ») :",
    "• Microsoft 365 : demandez à l'administrateur d'activer « SMTP authentifié » sur la boîte, ou "
    "d'utiliser une solution d'envoi dédiée Microsoft ;",
    "• sinon, utilisez une autre boîte d'envoi (Gmail, OVH, IONOS, Infomaniak, celle de votre FAI) : "
    "les destinataires peuvent rester des adresses Outlook."], "warn"))
add(P("5.3 Créer un mot de passe d'application Gmail", "h2"))
for s in steps([
    "Connectez-vous au compte Google qui enverra les scans, puis ouvrez <b>myaccount.google.com/security</b>.",
    "Activez la <b>Validation en deux étapes</b> si ce n'est pas déjà fait (obligatoire).",
    "Ouvrez <b>myaccount.google.com/apppasswords</b>, donnez un nom (ex. « Multifonction ») et "
    "cliquez sur <b>Créer</b>.",
    "Copiez le code de 16 lettres affiché et collez-le dans le champ <b>Mot de passe</b> du logiciel "
    "(les espaces n'ont pas d'importance). Ce code ne sera plus affiché ensuite.",
    "Pour Google Workspace, l'administrateur doit autoriser les mots de passe d'application."]):
    add(s)
add(CondPageBreak(14 * cm))
add(P("5.4 Démarrer le relais local", "h2"))
add(shot("6_relais.jpg", "Figure 4 — Section Relais SMTP local (bas de la page Scan vers e-mail)", width=13.5 * cm))
add(table([["Réglage", "Explication"],
           ["Port d'écoute", "25 par défaut : c'est le port standard. Toshiba et Lexmark permettent de changer le port SMTP : "
                             "2525 évite tout conflit avec un autre relais."],
           ["IP autorisées", "Vide = tout le réseau local (adresses privées). Pour plus de sécurité, "
                             "indiquez seulement l'IP de l'imprimante (ex. 192.168.1.50). Plusieurs "
                             "valeurs séparées par des virgules ; plages acceptées (192.168.1.0/24)."],
           ["Auth. (facultatif)", "Identifiant et mot de passe que l'imprimante devra fournir. Vide = "
                                  "aucune authentification (les IP restent filtrées)."],
           ["Transmettre au fournisseur", "Décochez si vous voulez seulement enregistrer les pièces jointes "
                                          "dans un dossier (voir 5.6)."],
           ["Adresse d'expédition du compte", "Remplace l'expéditeur de l'imprimante par l'adresse du compte "
                                              "(l'adresse d'origine est placée en « Répondre à »). Évite les "
                                              "refus anti-usurpation de Gmail, Microsoft, OVH…"],
           ["Enregistrer les pièces jointes", "Copie chaque document reçu dans le dossier indiqué, avec "
                                              "un sous-dossier par date si coché."]],
          [4.4 * cm, W - 4.4 * cm]))
add(Spacer(1, 6))
for s in steps([
    "Cliquez sur <b>Démarrer le relais</b>. L'état passe au vert et indique l'adresse et le port à saisir "
    "sur l'imprimante.",
    "Windows : cliquez sur <b>Autoriser dans le pare-feu</b> (droits administrateur demandés) pour que "
    "l'imprimante puisse joindre le port.",
    "Cliquez sur <b>Tester le relais</b> : un message de test passe par le relais exactement comme le "
    "ferait l'imprimante. Consultez la page <b>Journal</b> pour suivre son parcours."]):
    add(s)
add(P("5.5 Démarrage automatique", "h2"))
add(P("Cochez <b>Lancer le relais automatiquement à l'ouverture de session</b>. Le relais tourne alors en "
      "arrière-plan, sans fenêtre, dès que vous ouvrez votre session (raccourci dans le dossier Démarrage "
      "sous Windows, agent de lancement sous macOS). Vous pouvez fermer l'interface : le relais continue."))
add(box("Relais déjà en marche",
        "Si le relais automatique tourne déjà, le bouton « Démarrer le relais » de l'interface affiche "
        "« port déjà utilisé » : c'est normal, le relais fonctionne en arrière-plan. Utilisez « Tester le "
        "relais » pour le vérifier."))
add(P("5.6 Astuce : le scan vers dossier par e-mail", "h2"))
add(P("Si le partage SMB pose problème (Mac récent avec un très ancien multifonction, réseau d'entreprise "
      "restrictif…), activez <b>Enregistrer aussi les pièces jointes</b> et décochez <b>Transmettre au "
      "fournisseur</b>. Créez ensuite sur l'imprimante un destinataire e-mail quelconque (ex. "
      "<font name='Mono'>scans@bureau.local</font>) : chaque « envoi par e-mail » vers ce destinataire "
      "arrive directement dans le dossier de l'ordinateur, sans Internet ni compte de messagerie."))
add(P("5.7 Déclarer le serveur SMTP sur l'imprimante", "h2"))
add(table([["Marque", "Chemin dans l'interface Web"],
           ["Toshiba (TopAccess)", "Administration > Configuration > Réseau > <b>Client SMTP</b> (SMTP Client) ; "
            "l'adresse d'expéditeur se règle dans Administration > Configuration > <b>E-mail</b>."],
           ["Lexmark (EWS)", "Paramètres > E-mail > <b>Configuration de l'e-mail</b> (E-mail Setup). Anciens "
            "modèles : Paramètres > Réseau/Ports > Configuration SMTP."]], [4.3 * cm, W - 4.3 * cm]))
add(Spacer(1, 6))
add(P("Toshiba e-STUDIO", "h3"))
add(table([["Champ TopAccess", "Mode relais", "Mode direct (ex. Gmail)"],
           ["Activer le client SMTP", "Activé", "Activé"],
           ["Adresse du serveur SMTP", "IP du PC (ex. 192.168.1.25)", "smtp.gmail.com"],
           ["Numéro de port", "25 (ou celui choisi)", "587"],
           ["SSL/TLS", "Désactivé", "STARTTLS (465 : Over SSL)"],
           ["Authentification", "Désactivé (ou LOGIN si définie dans le relais)", "LOGIN ou Auto + nom de "
                                                                               "connexion + mot de passe d'application"],
           ["POP avant SMTP", "Désactivé", "Désactivé"],
           ["Adresse d'expéditeur (menu E-mail)", "adresse d'expédition", "votre.compte@gmail.com"]],
          [4.4 * cm, 5.4 * cm, W - 9.8 * cm]))
add(P("Lexmark", "h3"))
add(table([["Champ EWS", "Mode relais", "Mode direct (ex. Gmail)"],
           ["Passerelle SMTP principale", "IP du PC (ex. 192.168.1.25)", "smtp.gmail.com"],
           ["Port de la passerelle", "25 (ou celui choisi)", "587"],
           ["Utiliser SSL/TLS", "Désactivé", "Négocier (465 : Requis)"],
           ["Exiger un certificat approuvé", "Non", "Oui si le micrologiciel est à jour"],
           ["Adresse de réponse", "adresse d'expédition", "votre.compte@gmail.com"],
           ["Authentification serveur SMTP", "Aucune authentification requise (ou Login/Plain si définie)",
            "Login / Plain"],
           ["E-mail initié par le périphérique", "Aucun", "Utiliser les identifiants SMTP du périphérique : "
                                                         "ID + mot de passe d'application"]],
          [4.4 * cm, 5.4 * cm, W - 9.8 * cm]))
add(Spacer(1, 6))
add(P("En mode direct, le serveur DNS de l'imprimante doit être correctement renseigné. En mode relais, l'IP "
      "suffit : aucun DNS n'est nécessaire. Certains micrologiciels Lexmark récents proposent un bouton de test "
      "de la connexion SMTP : utilisez-le après l'enregistrement."))
add(PageBreak())

# ------------------------------------------------------------------ 6. Fiche imprimante
add(P("SECTION 6", "kicker")); add(P("Réglages à saisir sur l'imprimante", "h1"))
add(P("La page <b>Réglages imprimante</b> rassemble, à partir de vos choix, toutes les valeurs à recopier : "
      "destination réseau SMB, serveur SMTP, mode choisi, et où lire les erreurs. Les menus et intitulés "
      "s'adaptent à la marque choisie dans la page Accueil."))
add(shot("4_imprimante.jpg", "Figure 5 — Fiche générée pour un Toshiba e-STUDIO (menus TopAccess)", width=12.5 * cm))
add(shot("7_lexmark.jpg", "Figure 6 — La même fiche pour un Lexmark (menus de l'Embedded Web Server)", width=12.5 * cm))
add(P("<b>Copier</b> place la fiche dans le presse-papiers ; <b>Exporter (.txt)</b> l'enregistre pour la "
      "transmettre au technicien. La fiche contient les mots de passe en clair : conservez-la en lieu sûr."))
add(PageBreak())

# ------------------------------------------------------------------ 7. FILE_SHARE (Toshiba)
add(P("SECTION 7", "kicker")); add(P("Toshiba : dossier FILE_SHARE du copieur", "h1"))
add(P("Un e-STUDIO peut aussi enregistrer les numérisations dans son propre stockage interne (« Enregistrer en "
      "tant que fichier » vers le stockage local). Ces fichiers se récupèrent depuis l'ordinateur dans le dossier "
      "partagé <b>FILE_SHARE</b> du copieur, à l'adresse <font name='Mono'>\\\\IP-du-copieur\\FILE_SHARE</font>. "
      "La page <b>Dossier FILE_SHARE</b> du logiciel (visible quand la marque Toshiba est choisie) regroupe la "
      "procédure et les outils de vérification."))
add(shot("8_fileshare.jpg", "Figure 8 — Page Dossier FILE_SHARE", width=10.5 * cm))
add(P("Le problème", "h2"))
add(P("En tapant <font name='Mono'>\\\\IP-du-copieur</font> ou <font name='Mono'>\\\\IP-du-copieur\\FILE_SHARE</font> "
      "dans l'Explorateur Windows, une fenêtre demande un nom d'utilisateur et un mot de passe, et le dossier "
      "ne s'ouvre pas."))
add(P("La solution, constatée en intervention", "h2"))
for s_ in steps([
    "Ouvrez TopAccess avec le compte administrateur, puis <b>Administration</b> > <b>Configuration</b> > "
    "<b>Réseau</b> > <b>SMB</b>.",
    "Saisissez un <b>nom d'utilisateur</b> et un <b>mot de passe</b>, puis enregistrez.",
    "<b>Désactivez</b> ensuite cette authentification, puis enregistrez à nouveau.",
    "Rouvrez <font name='Mono'>\\\\IP-du-copieur\\FILE_SHARE</font> : le dossier s'ouvre sans demander "
    "d'identifiants."]):
    add(s_)
add(P("Vérifier depuis le logiciel", "h2"))
add(P("<b>Tester l'accès</b> tente d'ouvrir le dossier sans identifiants et explique le résultat : accès réussi, "
      "identifiants demandés par le copieur (appliquez la solution ci-dessus), accès invité refusé par Windows, "
      "serveur SMB du copieur inactif ou partage absent. <b>Ouvrir FILE_SHARE</b> ouvre le dossier dans "
      "l'Explorateur. La même procédure figure en section 4 de la fiche <b>Réglages imprimante</b>."))
add(box("Si la fenêtre d'identifiants persiste",
        "Saisissez dans Windows le nom d'utilisateur et le mot de passe définis à l'étape 2. Les intitulés des "
        "menus TopAccess varient selon le modèle et la version du micrologiciel."))
add(PageBreak())

# ------------------------------------------------------------------ 8. Dépannage
add(P("SECTION 8", "kicker")); add(P("Dépannage", "h1"))
add(P("Le journal", "h2"))
add(P("La page <b>Journal</b> affiche en direct chaque connexion de l'imprimante, chaque scan reçu, "
      "chaque fichier enregistré et chaque e-mail transmis. Le fichier journal complet est accessible par "
      "le bouton <b>Ouvrir le fichier journal</b>."))
add(shot("5_journal.jpg", "Figure 7 — Journal : réception d'un scan relayé et enregistré", width=12 * cm))
add(P("Où lire l'erreur côté imprimante", "h2"))
add(table([["Marque", "Emplacement"],
           ["Toshiba", "TopAccess > <b>Journaux</b> > Journal de numérisation / Journal d'envoi (code et cause de "
                       "l'échec) ; sur le panneau : État des travaux > Journal."],
           ["Lexmark", "Message affiché sur le panneau à la fin du travail ; EWS > <b>Rapports</b> ; bouton "
                       "<b>Tester la connexion</b> de la destination réseau ou de la configuration e-mail "
                       "(micrologiciels récents)."]], [3 * cm, W - 3 * cm]))
add(P("Scan vers dossier", "h2"))
add(table([["Symptôme", "Cause probable", "Solution"],
           ["Connexion impossible / délai dépassé", "Pare-feu, réseau en profil Public, PC en veille "
            "ou IP du PC changée.", "Recréer le partage avec les options pare-feu et profil Privé ; vérifier "
            "l'IP dans la page Accueil ; désactiver la mise en veille."],
           ["Échec sous Windows 11 24H2 alors que tout est correct", "Signature SMB exigée, non gérée "
            "par l'imprimante.", "Cocher « Ne pas exiger la signature SMB », recréer le partage. Mettre à "
            "jour le micrologiciel de l'imprimante."],
           ["Identifiant ou mot de passe refusé", "Mauvais format ou caractères spéciaux.", "Essayer "
            "NOMDUPC\\scanner ; régénérer un mot de passe sans caractères spéciaux."],
           ["Chemin introuvable", "Chemin mal saisi.", "Format exact : \\\\192.168.1.25\\SCANS "
            "(deux antislashs au début, un seul ensuite)."],
           ["Toshiba : échec malgré des identifiants corrects", "Version SMB ou signature côté imprimante.",
            "TopAccess > Administration > Configuration > Réseau > SMB : autoriser SMB 2/3 ; mettre à jour le "
            "micrologiciel."],
           ["Toshiba : \\\\IP\\FILE_SHARE demande un identifiant", "Authentification SMB du copieur.",
            "Voir section 7 (TopAccess > Réseau > SMB)."],
           ["Très ancien modèle, aucune connexion", "L'imprimante ne gère que SMB1.", "Préférer l'astuce 5.6 "
            "(scan par e-mail vers dossier). En dernier recours, option SMB1 (Windows uniquement)."],
           ["Mac : connexion refusée", "« Partage Windows » non activé pour le compte.", "Recréer le partage ; "
            "vérifier Réglages Système > Partage > Partage de fichiers > Options."],
           ["Le bouton Vérifier indique port 445 fermé", "Partage de fichiers désactivé ou bloqué par un "
            "antivirus tiers.", "Autoriser « Partage de fichiers » dans le pare-feu de l'antivirus."]],
          [4.2 * cm, 5 * cm, W - 9.2 * cm]))
add(P("Scan vers e-mail", "h2"))
add(table([["Symptôme", "Cause probable", "Solution"],
           ["Test d'envoi : erreur 535 / 534", "Identifiants refusés.", "Utiliser un mot de passe "
            "d'application ; vérifier l'identifiant complet ; voir l'encadré Microsoft (5.2)."],
           ["Test d'envoi : délai dépassé", "Port bloqué par le réseau ou l'antivirus.", "Essayer 465 SSL/TLS "
            "au lieu de 587 STARTTLS (ou l'inverse)."],
           ["Imprimante : serveur SMTP introuvable", "Nom de serveur non résolu.", "En mode relais : saisir l'IP "
            "du PC, pas son nom. En direct : vérifier le DNS de l'imprimante."],
           ["Imprimante : échec TLS / connexion en mode direct", "Chiffrement non supporté par l'imprimante.",
            "Passer en mode relais."],
           ["Imprimante : connexion refusée en mode relais", "Relais arrêté ou port bloqué.", "Démarrer le "
            "relais, cliquer sur « Autoriser dans le pare-feu », vérifier le port."],
           ["Message accepté mais jamais reçu", "Filtre anti-spam ou envoi en échec.", "Consulter le "
            "Journal : si « mis en file d'attente », corriger le compte ; le message repartira tout seul."],
           ["« Port déjà utilisé » au démarrage", "Relais automatique déjà actif, ou autre serveur sur le "
            "port 25.", "Tester le relais ; sinon choisir un autre port (ex. 2525) si l'imprimante le permet."],
           ["Journal : « Connexion refusée (IP non autorisée) »", "L'imprimante n'est pas dans la liste.",
            "Vider le champ IP autorisées ou y ajouter l'IP de l'imprimante."]],
          [4.2 * cm, 5 * cm, W - 9.2 * cm]))
add(Spacer(1, 6))
add(P("Les intitulés des messages d'erreur varient selon le modèle et la langue de l'imprimante. "
      "Consultez le manuel de votre modèle sur le site du constructeur pour le détail.", "small"))
add(PageBreak())

# ------------------------------------------------------------------ 8. Sécurité
add(P("SECTION 9", "kicker")); add(P("Sécurité, maintenance et désinstallation", "h1"))
add(P("Sécurité", "h2"))
for t in [
    "Le compte dédié n'a accès qu'au dossier des scans. Il ne peut pas ouvrir de session (masqué sous "
    "Windows, sans interpréteur de commandes sous macOS).",
    "Le relais SMTP n'accepte que les connexions du réseau local (ou des IP que vous indiquez) : il ne peut "
    "pas servir de relais ouvert depuis Internet. N'ouvrez jamais le port 25 de la box vers l'ordinateur.",
    "Entre l'imprimante et le PC, le trafic e-mail n'est pas chiffré : réservez le mode relais à un réseau "
    "local de confiance. Entre le PC et le fournisseur, il est toujours chiffré (STARTTLS ou SSL/TLS).",
    "Les mots de passe sont stockés dans le fichier de configuration de votre session utilisateur "
    "(<font name='Mono'>%APPDATA%\\ToshibaLexmarkScanSetup\\config.json</font> sous Windows, "
    "<font name='Mono'>~/Library/Application Support/ToshibaLexmarkScanSetup/</font> sous macOS), lisible par "
    "votre seul compte. Utilisez des mots de passe d'application, révocables à tout moment.",
    "Les options SMB1 et « signature SMB non exigée » réduisent la sécurité du partage : ne les activez "
    "que si l'imprimante l'impose, et de préférence mettez plutôt à jour son micrologiciel."]:
    add(Paragraph("•&nbsp;&nbsp;" + t, ParagraphStyle("b", parent=ss["body"], leftIndent=12, firstLineIndent=-12)))
add(P("Maintenance", "h2"))
add(table([["Situation", "Action"],
           ["L'IP du PC a changé", "Mettre à jour le chemin de la destination réseau et le serveur SMTP sur "
                                   "l'imprimante (la fiche Réglages imprimante affiche la nouvelle IP). Mieux : "
                                   "réservation DHCP."],
           ["Changer le mot de passe du compte scanner", "Saisir le nouveau mot de passe, cliquer sur « Créer "
                                                          "le partage » (le compte est mis à jour), puis "
                                                          "modifier le destinataire sur l'imprimante."],
           ["Mot de passe d'application révoqué", "En créer un nouveau, le saisir, « Tester l'envoi »."],
           ["Messages en file d'attente", "Ils sont renvoyés automatiquement ; bouton « Renvoyer la file "
                                          "d'attente » dans la page Journal pour forcer l'envoi."],
           ["Mode service (avancé)", "Le relais peut être lancé sans interface : "
                                     "<font name='Mono'>python ToshibaLexmarkScanSetup.py --relay</font>"]],
          [5 * cm, W - 5 * cm]))
add(P("Désinstallation", "h2"))
for s in steps([
    "Page Scan vers dossier : <b>Supprimer le partage</b>, puis confirmez la suppression du compte "
    "dédié si vous le souhaitez. Les fichiers déjà numérisés sont conservés.",
    "Page Scan vers e-mail : décochez le démarrage automatique et arrêtez le relais.",
    "Windows : supprimez la règle de pare-feu « Toshiba Lexmark Scan Relay SMTP » (Pare-feu Windows Defender > "
    "Paramètres avancés > Règles de trafic entrant), si elle a été créée.",
    "Supprimez le dossier ToshibaLexmarkScanSetup et le dossier de configuration indiqué ci-dessus.",
    "Sur l'imprimante, supprimez ou modifiez les destinataires et le serveur SMTP correspondants."]):
    add(s)

doc.build(S)
print("PDF OK:", OUT)




