import sys, tempfile, ctypes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import subprocess
from tlscan import config
tmp = Path(tempfile.mkdtemp()); config.config_dir = lambda: tmp
from tlscan import gui
ctypes.windll.shcore.SetProcessDpiAwareness(1)
out = Path(sys.argv[1]); out.mkdir(exist_ok=True)
app = gui.App()
app.v_printer.set("192.168.1.50"); app.v_pass.set("Scan-2026!Bx")
app.v_uuser.set("scans.bureau@gmail.com"); app.v_upass.set("abcd efgh ijkl mnop")
app.v_from.set("scans.bureau@gmail.com"); app.v_test_to.set("contact@mon-entreprise.fr")
app.v_save_att.set(True)
app.lbl_printer.config(text="✔ Imprimante joignable, interface Web disponible", style="Ok.TLabel")
app.lbl_up.config(text="✔ Message de test envoyé à contact@mon-entreprise.fr. Vérifiez la boîte de réception (et les indésirables).", style="Ok.TLabel")
app._set_text(app.txt_share, "Compte local 'scanner' créé.\nCompte masqué de l'écran de connexion.\nDossier prêt : C:\\Scans\nDroits NTFS 'Modification' accordés à scanner.\nPartage \\\\BUREAU-PC\\SCANS créé.\nPare-feu : « Partage de fichiers et d'imprimantes » autorisé (réseaux privés).\n\n✔ TERMINÉ. Sur l'imprimante, créez une destination « Fichier » :\n   Protocole : Windows (SMB)   Hôte : \\\\192.168.1.25\\SCANS\n   Utilisateur : scanner   Mot de passe : Scan-2026!Bx")
app.v_relay_status.set("En marche — 192.168.1.25:25"); app.lbl_relay.config(style="Ok.TLabel")
app.btn_relay.config(text="■ Arrêter le relais")
app.geometry("1120x800+40+20")
names = ["accueil", "dossier", "email", "imprimante", "journal", "relais", "lexmark", "fileshare"]
pages = {0: "home", 1: "folder", 2: "mail", 3: "printer", 4: "log", 5: "mail", 6: "printer", 7: "fileshare"}
import logging
lg = logging.getLogger("tlscan"); lg.setLevel(logging.INFO)
def step(i=0):
    if i == 4:
        for m in ["Relais SMTP démarré sur le port 25 (IP du PC : 192.168.1.25)", "Connexion de 192.168.1.50",
                  "Scan reçu de 192.168.1.50 (412 Ko) pour contact@mon-entreprise.fr",
                  "Pièce jointe enregistrée : C:\\Scans\\Mail\\2026-11-05\\093012_SCAN_0001.pdf",
                  "E-mail transmis via smtp.gmail.com à contact@mon-entreprise.fr"]:
            lg.info(m)
    if i >= len(names):
        app.destroy(); return
    if i == 6: app.v_brand.set("lexmark"); app._on_brand()
    if i == 7: app.v_brand.set("toshiba"); app._on_brand()
    app.show_page(pages[i]); app.update()
    if i == 5: app.pages["mail"]["canvas"].yview_moveto(1.0); app.update()
    app.after(900, lambda: grab(i))
def grab(i):
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    p = out / f"{i+1}_{names[i]}.png"
    ps = ("Add-Type -AssemblyName System.Drawing; Add-Type 'using System.Runtime.InteropServices; public class D{[DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware();}'; [D]::SetProcessDPIAware() | Out-Null;"
          f"$b=New-Object System.Drawing.Bitmap({w},{h}); $g=[System.Drawing.Graphics]::FromImage($b);"
          f"$g.CopyFromScreen({x},{y},0,0,$b.Size); $b.Save('{p}',[System.Drawing.Imaging.ImageFormat]::Png)")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    step(i + 1)
app.lift(); app.attributes("-topmost", True)
app.after(800, step)
app.mainloop()
print("done")



