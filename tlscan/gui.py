"""Interface graphique (tkinter) de Toshiba & Lexmark Scan Setup.

Mise en page : barre latérale de navigation (étapes numérotées) + pages qui défilent.
"""
import logging
import queue
import secrets
import string
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import APP_NAME, BRANDS, VERSION, autostart, printer_summary, config, mailer, netutil, sharing
from .config import IS_MAC, IS_WINDOWS
from .smtp_relay import RelayServer

log = logging.getLogger("tlscan")

# Palette
ACCENT = "#0B5C7A"        # bleu pétrole
ACCENT_DARK = "#084A63"
BG = "#FFFFFF"            # fond des pages
SOFT = "#F4F7F9"          # fonds secondaires (zones de texte)
BORDER = "#D9E1E7"
FIELD_BORDER = "#C3CDD5"
TEXT = "#1D2730"
MUTED = "#5E6B76"
OK = "#1A7F37"
ERR = "#B42318"
SIDE = "#0C2F3D"          # barre latérale
SIDE_HOVER = "#134152"
SIDE_SEL = "#0B5C7A"
SIDE_TXT = "#E8F2F6"
SIDE_MUTED = "#8DB0BE"

WRAP = 760                # largeur des paragraphes (pixels)


class _QueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.q = q

    def emit(self, record):
        self.q.put(self.format(record))


def _gen_password(n=12):
    alphabet = string.ascii_letters + string.digits + "-_.!"
    while True:
        p = "".join(secrets.choice(alphabet) for _ in range(n))
        if any(c.isdigit() for c in p) and any(c.isupper() for c in p) and any(c.islower() for c in p):
            return p


class App(tk.Tk):
    # clé, numéro, libellé, titre de page, sous-titre
    PAGES = [
        ("home", "1", "Accueil", "Bienvenue",
         "Choisissez la marque, saisissez l'adresse IP du multifonction et testez la connexion."),
        ("folder", "2", "Scan vers dossier", "Scan vers dossier partagé (SMB)",
         "L'imprimante dépose les fichiers numérisés dans un dossier partagé de ce PC, avec un compte dédié. "
         "Des droits administrateur seront demandés."),
        ("mail", "3", "Scan vers e-mail", "Scan vers e-mail (SMTP)",
         "Testez votre messagerie et, si l'imprimante ne gère pas le chiffrement moderne, utilisez ce PC "
         "comme relais SMTP."),
        ("printer", "4", "Réglages imprimante", "Réglages à saisir sur l'imprimante",
         "Recopiez ces valeurs dans TopAccess (Toshiba) ou l'Embedded Web Server (Lexmark)."),
        ("fileshare", "5", "Dossier FILE_SHARE", "Dossier FILE_SHARE du copieur Toshiba",
         "Récupérer depuis ce PC les scans enregistrés dans le stockage interne du copieur."),
        ("log", "≡", "Journal", "Journal des opérations", "Historique des actions et des messages du relais."),
    ]

    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        self.relay = None
        self.log_q = queue.Queue()
        h = _QueueHandler(self.log_q)
        h.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        logging.getLogger("tlscan").addHandler(h)

        self.title(f"{APP_NAME} {VERSION}")
        self._set_icon()
        self.geometry("1120x800")
        self.minsize(960, 620)
        self.configure(bg=BG)
        self._style()
        self._vars()
        self.pages, self.nav, self.current = {}, {}, None
        self._build()
        self.show_page("home")
        self.after(200, self._poll_log)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        """Icône de la fenêtre et de la barre des tâches (fichiers assets/, inclus dans l'exe)."""
        import os
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        assets = os.path.join(base, "assets")
        try:
            if IS_WINDOWS:
                self.iconbitmap(default=os.path.join(assets, "icon.ico"))
            self._icon_img = tk.PhotoImage(file=os.path.join(assets, "icon-256.png"))
            self.iconphoto(True, self._icon_img)
        except (tk.TclError, OSError):
            pass

    # ------------------------------------------------------------------ style
    def _style(self):
        base = ("Segoe UI", 10) if IS_WINDOWS else ("Helvetica Neue", 13) if IS_MAC else ("DejaVu Sans", 10)
        self.base_font = base
        fam, size = base
        from tkinter import font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=fam, size=size)
            except tk.TclError:
                pass
        self.option_add("*TCombobox*Listbox.background", "white")
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.font", base)

        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=TEXT, font=base, bordercolor=BORDER,
                     lightcolor=BG, darkcolor=BG, troughcolor=SOFT, focuscolor=ACCENT,
                     selectbackground=ACCENT, selectforeground="white")
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=TEXT)
        st.configure("Title.TLabel", font=(fam, size + 9, "bold"), foreground=TEXT)
        st.configure("Sub.TLabel", foreground=MUTED)
        st.configure("H.TLabel", font=(fam, size + 1, "bold"))
        st.configure("Muted.TLabel", foreground=MUTED)
        st.configure("Ok.TLabel", foreground=OK)
        st.configure("Err.TLabel", foreground=ERR)
        st.configure("Num.TLabel", foreground="white", background=ACCENT, font=(fam, size, "bold"),
                     anchor="center", padding=(7, 1))
        st.configure("Card.TLabelframe", background=BG, bordercolor=BORDER, relief="solid", borderwidth=1)
        st.configure("Card.TLabelframe.Label", background=BG, foreground=ACCENT, font=(fam, size + 1, "bold"))

        st.configure("TButton", background="#EEF2F5", foreground=TEXT, bordercolor=FIELD_BORDER,
                     lightcolor="#EEF2F5", darkcolor="#EEF2F5", padding=(12, 5), relief="flat")
        st.map("TButton",
               background=[("pressed", "#D5DEE5"), ("active", "#E1E8EE")],
               lightcolor=[("pressed", "#D5DEE5"), ("active", "#E1E8EE")],
               darkcolor=[("pressed", "#D5DEE5"), ("active", "#E1E8EE")])
        st.configure("Accent.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT,
                     lightcolor=ACCENT, darkcolor=ACCENT, font=(fam, size, "bold"), padding=(14, 6))
        st.map("Accent.TButton",
               background=[("pressed", ACCENT_DARK), ("active", ACCENT_DARK)],
               lightcolor=[("pressed", ACCENT_DARK), ("active", ACCENT_DARK)],
               darkcolor=[("pressed", ACCENT_DARK), ("active", ACCENT_DARK)],
               bordercolor=[("active", ACCENT_DARK)])

        st.configure("TEntry", fieldbackground="white", bordercolor=FIELD_BORDER, lightcolor="white",
                     darkcolor="white", padding=5)
        st.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
        st.configure("TCombobox", fieldbackground="white", background="#EEF2F5", bordercolor=FIELD_BORDER,
                     lightcolor="white", darkcolor="white", arrowcolor=TEXT, padding=4)
        st.map("TCombobox", fieldbackground=[("readonly", "white")], selectbackground=[("readonly", "white")],
               selectforeground=[("readonly", TEXT)], bordercolor=[("focus", ACCENT)])
        for w in ("TCheckbutton", "TRadiobutton"):
            st.configure(w, background=BG, indicatorbackground="white", indicatorforeground="white",
                         upperbordercolor="#8C9AA6", lowerbordercolor="#8C9AA6", padding=(0, 3),
                         indicatorsize=15, indicatordiameter=15, indicatormargin=(0, 0, 8, 0))
            st.map(w, indicatorbackground=[("selected", ACCENT), ("pressed", "#DCE5EB")],
                   background=[("active", BG)])
        st.configure("Vertical.TScrollbar", background="#D3DBE1", troughcolor=BG, bordercolor=BG,
                     lightcolor="#D3DBE1", darkcolor="#D3DBE1", arrowcolor=MUTED, gripcount=0)
        st.map("Vertical.TScrollbar", background=[("active", "#B9C5CE")])
        st.configure("Horizontal.TScrollbar", background="#D3DBE1", troughcolor=BG, bordercolor=BG,
                     lightcolor="#D3DBE1", darkcolor="#D3DBE1", arrowcolor=MUTED, gripcount=0)
        st.map("Horizontal.TScrollbar", background=[("active", "#B9C5CE")])

    # ------------------------------------------------------------------ variables
    def _vars(self):
        c = self.cfg
        self.v_printer = tk.StringVar(value=c["printer_ip"])
        self.v_brand = tk.StringVar(value=c.get("brand", "toshiba"))
        s = c["share"]
        self.v_folder = tk.StringVar(value=s["folder"])
        self.v_share = tk.StringVar(value=s["share_name"])
        self.v_user = tk.StringVar(value=s["username"])
        self.v_pass = tk.StringVar(value=s["password"] or _gen_password())
        self.v_create_user = tk.BooleanVar(value=s["create_user"])
        self.v_fw = tk.BooleanVar(value=s["open_firewall"])
        self.v_private = tk.BooleanVar(value=s["set_private_network"])
        self.v_signing = tk.BooleanVar(value=s["disable_smb_signing"])
        self.v_smb1 = tk.BooleanVar(value=s["enable_smb1"])
        u = c["upstream"]
        self.v_provider = tk.StringVar(value=u["provider"])
        self.v_host = tk.StringVar(value=u["host"])
        self.v_port = tk.StringVar(value=str(u["port"]))
        self.v_sec = tk.StringVar(value=mailer.SECURITY_LABELS[u["security"]])
        self.v_uuser = tk.StringVar(value=u["username"])
        self.v_upass = tk.StringVar(value=u["password"])
        self.v_from = tk.StringVar(value=u["from_addr"])
        self.v_test_to = tk.StringVar(value=u["test_to"])
        r = c["relay"]
        self.v_mode = tk.StringVar(value=r["mode"])
        self.v_lport = tk.StringVar(value=str(r["listen_port"]))
        self.v_allowed = tk.StringVar(value=r["allowed_ips"])
        self.v_rauth_user = tk.StringVar(value=r["auth_user"])
        self.v_rauth_pass = tk.StringVar(value=r["auth_password"])
        self.v_forward = tk.BooleanVar(value=r["forward_email"])
        self.v_rewrite = tk.BooleanVar(value=r["rewrite_from"])
        self.v_save_att = tk.BooleanVar(value=r["save_attachments"])
        self.v_save_folder = tk.StringVar(value=r["save_folder"])
        self.v_by_date = tk.BooleanVar(value=r["subfolder_by_date"])
        self.v_autostart = tk.BooleanVar(value=autostart.is_enabled())
        self.v_relay_status = tk.StringVar(value="Arrêté")
        self.v_fs_path = tk.StringVar()

    def _collect(self) -> dict:
        sec_rev = {v: k for k, v in mailer.SECURITY_LABELS.items()}

        def _int(v, default):
            try:
                return int(str(v).strip())
            except ValueError:
                return default

        c = self.cfg
        c["printer_ip"] = self.v_printer.get().strip()
        c["brand"] = self.v_brand.get()
        c["share"].update(folder=self.v_folder.get().strip(), share_name=self.v_share.get().strip(),
                          username=self.v_user.get().strip(), password=self.v_pass.get(),
                          create_user=self.v_create_user.get(), open_firewall=self.v_fw.get(),
                          set_private_network=self.v_private.get(), disable_smb_signing=self.v_signing.get(),
                          enable_smb1=self.v_smb1.get())
        c["upstream"].update(provider=self.v_provider.get(), host=self.v_host.get().strip(),
                             port=_int(self.v_port.get(), 587), security=sec_rev.get(self.v_sec.get(), "starttls"),
                             username=self.v_uuser.get().strip(), password=self.v_upass.get(),
                             from_addr=self.v_from.get().strip(), test_to=self.v_test_to.get().strip())
        c["relay"].update(mode=self.v_mode.get(), listen_port=_int(self.v_lport.get(), 25),
                          allowed_ips=self.v_allowed.get().strip(), auth_user=self.v_rauth_user.get().strip(),
                          auth_password=self.v_rauth_pass.get(), forward_email=self.v_forward.get(),
                          rewrite_from=self.v_rewrite.get(), save_attachments=self.v_save_att.get(),
                          save_folder=self.v_save_folder.get().strip(), subfolder_by_date=self.v_by_date.get(),
                          autostart=self.v_autostart.get())
        return c

    def save(self, quiet=False):
        config.save(self._collect())
        self._refresh_summary()
        if not quiet:
            log.info("Configuration enregistrée (%s)", config.config_path())

    # ------------------------------------------------------------------ squelette
    def _build(self):
        fam, size = self.base_font

        # ---- barre latérale
        side = self.sidebar = tk.Frame(self, bg=SIDE, width=252)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = tk.Frame(side, bg=SIDE)
        brand.pack(fill="x", padx=20, pady=(22, 18))
        tk.Label(brand, text="Toshiba & Lexmark", bg=SIDE, fg="white", anchor="w",
                 font=(fam, size + 3, "bold")).pack(fill="x")
        tk.Label(brand, text="Scan Setup", bg=SIDE, fg=SIDE_TXT, anchor="w",
                 font=(fam, size + 3)).pack(fill="x")
        tk.Label(brand, text=f"Version {VERSION}", bg=SIDE, fg=SIDE_MUTED, anchor="w").pack(fill="x", pady=(4, 0))
        tk.Frame(side, bg=SIDE_HOVER, height=1).pack(fill="x", padx=16, pady=(0, 10))
        self.nav_box = tk.Frame(side, bg=SIDE)
        self.nav_box.pack(fill="x")
        for key, num, label, *_ in self.PAGES:
            self._nav_item(key, num, label)

        foot = tk.Frame(side, bg=SIDE)
        foot.pack(side="bottom", fill="x", padx=20, pady=18)
        tk.Label(foot, text="RELAIS SMTP", bg=SIDE, fg=SIDE_MUTED, anchor="w",
                 font=(fam, size - 1, "bold")).pack(fill="x")
        self.lbl_side_relay = tk.Label(foot, text="●  Arrêté", bg=SIDE, fg="#F2A097", anchor="w")
        self.lbl_side_relay.pack(fill="x", pady=(2, 8))
        tk.Label(foot, text=f"IP de ce PC : {netutil.local_ip()}", bg=SIDE, fg=SIDE_MUTED, anchor="w").pack(fill="x")

        # ---- zone principale
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        head = ttk.Frame(main, padding=(28, 22, 28, 10))
        head.pack(fill="x")
        self.lbl_title = ttk.Label(head, text="", style="Title.TLabel")
        self.lbl_title.pack(anchor="w")
        self.lbl_sub = ttk.Label(head, text="", style="Sub.TLabel", wraplength=WRAP, justify="left")
        self.lbl_sub.pack(anchor="w", pady=(2, 0))

        bar = tk.Frame(main, bg=SOFT, highlightthickness=0)
        bar.pack(side="bottom", fill="x")
        tk.Frame(main, bg=BORDER, height=1).pack(side="bottom", fill="x")
        tk.Label(bar, text=f"Configuration : {config.config_path()}", bg=SOFT, fg=MUTED).pack(
            side="left", padx=28, pady=10)
        ttk.Button(bar, text="Enregistrer", style="Accent.TButton", command=self.save).pack(
            side="right", padx=28, pady=8)

        self.content = ttk.Frame(main)
        self.content.pack(fill="both", expand=True)

        for key, _num, _label, title, sub in self.PAGES:
            scroll = key not in ("printer", "log")
            self.pages[key] = self._make_page(key, title, sub, scroll)
        self._build_home()
        self._build_folder()
        self._build_mail()
        self._build_printer()
        self._build_fileshare()
        self._build_log()
        self._update_nav_visibility()
        self.bind_all("<MouseWheel>", self._on_wheel)
        if not IS_WINDOWS and not IS_MAC:
            self.bind_all("<Button-4>", lambda e: self._wheel_scroll(-1))
            self.bind_all("<Button-5>", lambda e: self._wheel_scroll(1))

    def _nav_item(self, key, num, label):
        fam, size = self.base_font
        fr = tk.Frame(self.nav_box, bg=SIDE, cursor="hand2")
        bar = tk.Frame(fr, bg=SIDE, width=4)
        bar.pack(side="left", fill="y")
        badge = tk.Label(fr, text=num, bg=SIDE, fg=SIDE_MUTED, width=2, font=(fam, size, "bold"))
        badge.pack(side="left", padx=(14, 8), pady=10)
        lbl = tk.Label(fr, text=label, bg=SIDE, fg=SIDE_TXT, anchor="w", font=(fam, size + 1))
        lbl.pack(side="left", fill="x", expand=True)
        fr.pack(fill="x")
        self.nav[key] = (fr, bar, badge, lbl)
        for w in (fr, badge, lbl):
            w.bind("<Button-1>", lambda e, k=key: self.show_page(k))
            w.bind("<Enter>", lambda e, k=key: self._paint_nav(k, hover=True))
            w.bind("<Leave>", lambda e, k=key: self._paint_nav(k))

    def _paint_nav(self, key, hover=False):
        fr, bar, badge, lbl = self.nav[key]
        sel = key == self.current
        bg = SIDE_SEL if sel else SIDE_HOVER if hover else SIDE
        for w in (fr, badge, lbl):
            w.configure(bg=bg)
        bar.configure(bg="#7FD0EA" if sel else bg)
        badge.configure(fg="white" if sel else SIDE_MUTED)
        lbl.configure(fg="white" if sel else SIDE_TXT)

    def _update_nav_visibility(self):
        fr = self.nav["fileshare"][0]
        if self.v_brand.get() == "toshiba":
            fr.pack(fill="x", before=self.nav["log"][0])
        else:
            fr.pack_forget()
            if self.current == "fileshare":
                self.show_page("home")

    def _make_page(self, key, title, sub, scroll):
        outer = ttk.Frame(self.content)
        canvas = None
        if scroll:
            canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0, background=BG)
            sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
            inner = ttk.Frame(canvas, padding=(28, 6, 28, 24))
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            win = canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

            def yset(lo, hi):
                if float(lo) <= 0.0 and float(hi) >= 1.0:
                    sb.pack_forget()
                elif not sb.winfo_ismapped():
                    sb.pack(side="right", fill="y", before=canvas)
                sb.set(lo, hi)
            canvas.configure(yscrollcommand=yset)
            canvas.pack(side="left", fill="both", expand=True)
        else:
            inner = ttk.Frame(outer, padding=(28, 6, 28, 20))
            inner.pack(fill="both", expand=True)
        return {"outer": outer, "inner": inner, "canvas": canvas, "title": title, "sub": sub}

    def show_page(self, key):
        if self.current and self.current in self.pages:
            self.pages[self.current]["outer"].pack_forget()
        prev, self.current = self.current, key
        p = self.pages[key]
        p["outer"].pack(fill="both", expand=True)
        if p["canvas"] is not None:
            p["canvas"].yview_moveto(0)
        self.lbl_title.config(text=p["title"])
        self.lbl_sub.config(text=p["sub"])
        for k in self.nav:
            self._paint_nav(k)
        if key == "printer":
            self._refresh_summary()
        elif key == "fileshare":
            self._refresh_fileshare_path()

    def _on_wheel(self, e):
        try:
            if isinstance(e.widget, (tk.Text, tk.Listbox)) or str(e.widget).endswith("listbox"):
                return
        except Exception:
            pass
        self._wheel_scroll(int(-e.delta / (1 if IS_MAC else 120)) or (-1 if e.delta > 0 else 1))

    def _wheel_scroll(self, units):
        p = self.pages.get(self.current)
        c = p and p["canvas"]
        if c is None:
            return
        lo, hi = c.yview()
        if lo <= 0 and hi >= 1:
            return
        c.yview_scroll(units, "units")

    # ------------------------------------------------------------------ aides de mise en page
    @staticmethod
    def _section(parent, title, pady=(0, 16)):
        lf = ttk.LabelFrame(parent, text=f" {title} ", padding=(16, 10, 16, 14), style="Card.TLabelframe")
        lf.pack(fill="x", pady=pady)
        return lf

    @staticmethod
    def _row(parent, r, label, widget, hint=None):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=4, padx=(0, 14))
        widget.grid(row=r, column=1, sticky="we", pady=4)
        if hint:
            ttk.Label(parent, text=hint, style="Muted.TLabel", wraplength=230, justify="left").grid(
                row=r, column=2, sticky="w", padx=10)

    def _text_box(self, parent, height):
        t = tk.Text(parent, height=height, wrap="word", relief="flat", borderwidth=0, font=self.base_font,
                    padx=10, pady=8, background=SOFT, foreground=TEXT, highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=BORDER)
        return t

    def _run_bg(self, fn, done):
        """Exécute fn() dans un thread puis done(result) dans l'interface."""
        self.config(cursor="watch")

        def worker():
            try:
                res = (True, fn())
            except Exception as e:
                res = (False, e)
            self.after(0, lambda: (self.config(cursor=""), done(*res)))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ 1. Accueil
    def _build_home(self):
        f = self.pages["home"]["inner"]

        box = self._section(f, "Imprimante")
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="Marque").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 14))
        bf = ttk.Frame(box)
        for key, label in BRANDS.items():
            ttk.Radiobutton(bf, text=label, value=key, variable=self.v_brand,
                            command=self._on_brand).pack(side="left", padx=(0, 22))
        bf.grid(row=0, column=1, columnspan=2, sticky="w", pady=4)
        self._row(box, 1, "Adresse IP", ttk.Entry(box, textvariable=self.v_printer, width=24),
                  "affichée sur l'écran du copieur ou la page de configuration réseau")
        btns = ttk.Frame(box)
        btns.grid(row=2, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(btns, text="Tester la connexion", style="Accent.TButton",
                   command=self._test_printer).pack(side="left")
        ttk.Button(btns, text="Ouvrir l'interface Web (TopAccess / EWS)",
                   command=self._open_rui).pack(side="left", padx=8)
        self.lbl_printer = ttk.Label(box, text="", wraplength=WRAP - 160, justify="left")
        self.lbl_printer.grid(row=3, column=1, columnspan=2, sticky="w", pady=(8, 0))

        pc = self._section(f, "Ce PC")
        osname = "Windows" if IS_WINDOWS else "macOS" if IS_MAC else sys.platform
        for i, (k, v) in enumerate([("Système", osname), ("Nom du PC", netutil.hostname()),
                                    ("Adresse IP locale", netutil.local_ip())]):
            ttk.Label(pc, text=k, style="Muted.TLabel").grid(row=0, column=i, sticky="w", padx=(0, 48))
            ttk.Label(pc, text=v, style="H.TLabel").grid(row=1, column=i, sticky="w", padx=(0, 48))

        steps = self._section(f, "Étapes de configuration")
        steps.columnconfigure(1, weight=1)
        self.home_steps = []
        rows = [
            ("2", "Scan vers dossier", "Créer le dossier partagé, le compte « scanner » et ouvrir le pare-feu.", "folder"),
            ("3", "Scan vers e-mail", "Choisir le fournisseur, tester l'envoi et démarrer le relais.", "mail"),
            ("4", "Réglages imprimante", "Recopier les valeurs dans TopAccess ou l'EWS.", "printer"),
            ("5", "Dossier FILE_SHARE (Toshiba)", "Ouvrir les scans stockés sur le copieur, sans identifiants.",
             "fileshare"),
        ]
        for i, (num, title, desc, key) in enumerate(rows):
            w = [ttk.Label(steps, text=num, style="Num.TLabel")]
            w[0].grid(row=i * 2, column=0, rowspan=2, sticky="n", padx=(0, 14), pady=(6, 0))
            w.append(ttk.Label(steps, text=title, style="H.TLabel"))
            w[1].grid(row=i * 2, column=1, sticky="w", pady=(6, 0))
            w.append(ttk.Label(steps, text=desc, style="Muted.TLabel"))
            w[2].grid(row=i * 2 + 1, column=1, sticky="w", pady=(0, 6))
            w.append(ttk.Button(steps, text="Ouvrir  →", command=lambda k=key: self.show_page(k)))
            w[3].grid(row=i * 2, column=2, rowspan=2, sticky="e", padx=(10, 0))
            self.home_steps.append((key, w))
        self._update_home_steps()

    def _update_home_steps(self):
        for key, widgets in getattr(self, "home_steps", []):
            for w in widgets:
                if key == "fileshare" and self.v_brand.get() != "toshiba":
                    w.grid_remove()
                else:
                    w.grid()

    def _on_brand(self):
        self._update_nav_visibility()
        self._update_home_steps()
        self._refresh_summary()

    def _test_printer(self):
        ip = self.v_printer.get().strip()
        if not ip:
            return messagebox.showwarning(APP_NAME, "Saisissez l'adresse IP de l'imprimante.")
        self.lbl_printer.config(text="Test en cours…", style="TLabel")

        def check():
            return netutil.ping(ip), netutil.port_open(ip, 80) or netutil.port_open(ip, 443) \
                or netutil.port_open(ip, 8000) or netutil.port_open(ip, 8447)

        def done(ok, res):
            if not ok:
                return self.lbl_printer.config(text=str(res), style="Err.TLabel")
            pong, web = res
            if web:
                self.lbl_printer.config(text="✔ Imprimante joignable, interface Web disponible", style="Ok.TLabel")
            elif pong:
                self.lbl_printer.config(text="⚠ Répond au ping, mais l'interface Web est fermée "
                                             "(activer le serveur HTTP de l'imprimante)", style="Err.TLabel")
            else:
                self.lbl_printer.config(text="✘ Imprimante injoignable : vérifiez l'IP et le réseau",
                                        style="Err.TLabel")
            self.save(quiet=True)
        self._run_bg(check, done)

    def _open_rui(self):
        ip = self.v_printer.get().strip()
        if not ip:
            return messagebox.showwarning(APP_NAME, "Saisissez l'adresse IP de l'imprimante (page Accueil).")
        webbrowser.open(f"http://{ip}/")

    # ------------------------------------------------------------------ 2. Dossier
    def _build_folder(self):
        f = self.pages["folder"]["inner"]

        g = self._section(f, "Paramètres du partage")
        g.columnconfigure(1, weight=1)
        fr = ttk.Frame(g)
        ttk.Entry(fr, textvariable=self.v_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(fr, text="Parcourir…", command=lambda: self._browse(self.v_folder)).pack(side="left", padx=(6, 0))
        self._row(g, 0, "Dossier de réception", fr)
        self._row(g, 1, "Nom du partage", ttk.Entry(g, textvariable=self.v_share, width=20), "sans espace, ex : SCANS")
        self._row(g, 2, "Compte utilisateur", ttk.Entry(g, textvariable=self.v_user, width=20), "ex : scanner")
        pf = ttk.Frame(g)
        ttk.Entry(pf, textvariable=self.v_pass, width=20).pack(side="left")
        ttk.Button(pf, text="Générer", command=lambda: self.v_pass.set(_gen_password())).pack(side="left", padx=6)
        self._row(g, 3, "Mot de passe", pf, "8 caractères min., sans guillemets")

        o = self._section(f, "Options")
        ttk.Checkbutton(o, text="Créer / mettre à jour le compte local dédié (recommandé)",
                        variable=self.v_create_user).pack(anchor="w")
        if IS_WINDOWS:
            ttk.Checkbutton(o, text="Ouvrir le pare-feu Windows (Partage de fichiers, réseaux privés)",
                            variable=self.v_fw).pack(anchor="w")
            ttk.Checkbutton(o, text="Passer le réseau actuel en profil « Privé » (sinon le partage est bloqué)",
                            variable=self.v_private).pack(anchor="w")
            ttk.Checkbutton(o, text="Compatibilité anciens modèles : ne pas exiger la signature SMB "
                                    "(Windows 11 24H2+)", variable=self.v_signing).pack(anchor="w")
            ttk.Checkbutton(o, text="Très anciens modèles (avant ~2015) : activer SMB1 — déconseillé, redémarrage requis",
                            variable=self.v_smb1).pack(anchor="w")

        a = self._section(f, "Actions")
        b = ttk.Frame(a)
        b.pack(fill="x")
        ttk.Button(b, text="Créer le partage", style="Accent.TButton", command=self._create_share).pack(side="left")
        ttk.Button(b, text="Vérifier", command=self._check_share).pack(side="left", padx=6)
        ttk.Button(b, text="Ouvrir le dossier", command=lambda: self._open_path(self.v_folder.get())).pack(side="left")
        ttk.Button(b, text="Supprimer le partage", command=self._remove_share).pack(side="right")
        self.txt_share = self._text_box(a, 9)
        self.txt_share.pack(fill="x", pady=(12, 0))
        self._set_text(self.txt_share, "Le résultat des opérations s'affichera ici.")

    def _browse(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or None)
        if d:
            var.set(d.replace("/", "\\") if IS_WINDOWS else d)

    @staticmethod
    def _open_path(p):
        try:
            if IS_WINDOWS:
                subprocess.Popen(["explorer", p])
            elif IS_MAC:
                subprocess.Popen(["open", p])
            else:
                subprocess.Popen(["xdg-open", p])
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    @staticmethod
    def _set_text(w, text):
        w.config(state="normal")
        w.delete("1.0", "end")
        w.insert("1.0", text)
        w.config(state="disabled")

    def _create_share(self):
        self.save(quiet=True)
        s = self.cfg["share"]
        errs = sharing.validate(s)
        if errs:
            return messagebox.showerror(APP_NAME, "\n".join(errs))
        self._set_text(self.txt_share, "Configuration en cours… acceptez la demande d'autorisation administrateur.")
        log.info("Création du partage %s -> %s", s["share_name"], s["folder"])

        def done(ok, res):
            if not ok:
                return self._set_text(self.txt_share, f"Erreur : {res}")
            success, out = res
            ip = netutil.local_ip()
            if success:
                out += (f"\n\n✔ TERMINÉ. Sur l'imprimante, créez la destination réseau (voir étape 4) :\n"
                        f"   Protocole : SMB   Chemin : \\\\{ip}\\{s['share_name']}\n"
                        f"   Utilisateur : {s['username']}   Mot de passe : {s['password']}")
                log.info("Partage créé avec succès")
            else:
                log.error("Échec de création du partage")
            self._set_text(self.txt_share, out)
            self._refresh_summary()
        self._run_bg(lambda: sharing.create_share(s), done)

    def _check_share(self):
        self.save(quiet=True)
        s = self.cfg["share"]
        self._run_bg(lambda: sharing.check_share(s, netutil.local_ip()),
                     lambda ok, res: self._set_text(self.txt_share, res[1] if ok else str(res)))

    def _remove_share(self):
        s = self._collect()["share"]
        if not messagebox.askyesno(APP_NAME, f"Supprimer le partage « {s['share_name']} » ?\n"
                                             "(les fichiers déjà scannés sont conservés)"):
            return
        del_user = s["create_user"] and messagebox.askyesno(APP_NAME, f"Supprimer aussi le compte « {s['username']} » ?")
        self._run_bg(lambda: sharing.remove_share(s, del_user),
                     lambda ok, res: self._set_text(self.txt_share, res[1] if ok else str(res)))

    # ------------------------------------------------------------------ 3. E-mail
    def _build_mail(self):
        f = self.pages["mail"]["inner"]

        m = self._section(f, "Mode d'envoi")
        ttk.Radiobutton(m, text="Relais via ce PC (recommandé) : imprimante → ce PC (sans TLS) → fournisseur (TLS)",
                        value="relay", variable=self.v_mode, command=self._refresh_summary).pack(anchor="w")
        ttk.Radiobutton(m, text="Direct : l'imprimante contacte elle-même le fournisseur (modèles récents, TLS 1.2)",
                        value="direct", variable=self.v_mode, command=self._refresh_summary).pack(anchor="w")

        u = self._section(f, "Compte de messagerie (serveur SMTP du fournisseur)")
        u.columnconfigure(1, weight=1)
        cb = ttk.Combobox(u, textvariable=self.v_provider, values=list(mailer.PROVIDERS), state="readonly", width=30)
        cb.bind("<<ComboboxSelected>>", self._on_provider)
        self._row(u, 0, "Fournisseur", cb)
        hp = ttk.Frame(u)
        ttk.Entry(hp, textvariable=self.v_host, width=24).pack(side="left", fill="x", expand=True)
        ttk.Label(hp, text="  Port").pack(side="left")
        ttk.Entry(hp, textvariable=self.v_port, width=6).pack(side="left", padx=4)
        ttk.Label(hp, text=" Sécurité").pack(side="left")
        ttk.Combobox(hp, textvariable=self.v_sec, values=list(mailer.SECURITY_LABELS.values()),
                     state="readonly", width=10).pack(side="left", padx=4)
        hp.grid(row=1, column=1, columnspan=2, sticky="we", pady=4)
        ttk.Label(u, text="Serveur SMTP").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 14))
        self._row(u, 2, "Identifiant", ttk.Entry(u, textvariable=self.v_uuser), "souvent l'adresse e-mail complète")
        self._row(u, 3, "Mot de passe", ttk.Entry(u, textvariable=self.v_upass, show="•"), "mot de passe d'application")
        self._row(u, 4, "Adresse d'expédition", ttk.Entry(u, textvariable=self.v_from), "vide = identifiant")
        self.lbl_provider = ttk.Label(u, text="", style="Muted.TLabel", wraplength=WRAP - 40, justify="left")
        self.lbl_provider.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._on_provider(init=True)
        t = ttk.Frame(u)
        t.grid(row=6, column=0, columnspan=3, sticky="we", pady=(10, 0))
        ttk.Label(t, text="Envoyer un test à :").pack(side="left")
        ttk.Entry(t, textvariable=self.v_test_to, width=30).pack(side="left", padx=6)
        ttk.Button(t, text="Tester l'envoi", style="Accent.TButton", command=self._test_upstream).pack(side="left")
        self.lbl_up = ttk.Label(u, text="", wraplength=WRAP - 40, justify="left")
        self.lbl_up.grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))

        r = self._section(f, "Relais SMTP local (mode « Relais via ce PC »)")
        r.columnconfigure(1, weight=1)
        self._row(r, 0, "Port d'écoute", ttk.Entry(r, textvariable=self.v_lport, width=8),
                  "25 = standard (sinon 2525 si réglable)")
        self._row(r, 1, "IP autorisées", ttk.Entry(r, textvariable=self.v_allowed),
                  "vide = tout le réseau local")
        au = ttk.Frame(r)
        ttk.Entry(au, textvariable=self.v_rauth_user, width=14).pack(side="left")
        ttk.Label(au, text="  Mot de passe").pack(side="left")
        ttk.Entry(au, textvariable=self.v_rauth_pass, width=14).pack(side="left", padx=(6, 0))
        self._row(r, 2, "Auth. (facultatif)", au, "vide = aucune")
        opts = ttk.Frame(r)
        opts.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(opts, text="Transmettre les e-mails au fournisseur", variable=self.v_forward).pack(anchor="w")
        ttk.Checkbutton(opts, text="Utiliser l'adresse d'expédition du compte (évite les refus anti-usurpation)",
                        variable=self.v_rewrite).pack(anchor="w")
        ttk.Checkbutton(opts, text="Enregistrer aussi les pièces jointes dans un dossier (scan vers dossier sans SMB)",
                        variable=self.v_save_att).pack(anchor="w")
        sf = ttk.Frame(r)
        ttk.Entry(sf, textvariable=self.v_save_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(sf, text="Parcourir…", command=lambda: self._browse(self.v_save_folder)).pack(side="left", padx=6)
        ttk.Checkbutton(sf, text="sous-dossier par date", variable=self.v_by_date).pack(side="left", padx=(4, 0))
        ttk.Label(r, text="Pièces jointes dans").grid(row=4, column=0, sticky="w", pady=4, padx=(0, 14))
        sf.grid(row=4, column=1, columnspan=2, sticky="we", pady=4)

        ctl = ttk.Frame(r)
        ctl.grid(row=5, column=0, columnspan=3, sticky="we", pady=(12, 0))
        self.btn_relay = ttk.Button(ctl, text="▶ Démarrer le relais", style="Accent.TButton", command=self._toggle_relay)
        self.btn_relay.pack(side="left")
        ttk.Button(ctl, text="Tester le relais", command=self._test_relay).pack(side="left", padx=6)
        if IS_WINDOWS:
            ttk.Button(ctl, text="Autoriser dans le pare-feu", command=self._fw_relay).pack(side="left")
        st = ttk.Frame(r)
        st.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(st, text="État du relais :").pack(side="left")
        self.lbl_relay = ttk.Label(st, textvariable=self.v_relay_status, style="Err.TLabel")
        self.lbl_relay.pack(side="left", padx=6)
        ttk.Checkbutton(r, text="Lancer le relais automatiquement à l'ouverture de session (en arrière-plan)",
                        variable=self.v_autostart, command=self._toggle_autostart).grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))
        q = mailer.queue_size()
        if q:
            ttk.Label(r, text=f"{q} message(s) en attente d'envoi", style="Err.TLabel").grid(
                row=8, column=0, columnspan=3, sticky="w")

    def _on_provider(self, event=None, init=False):
        name = self.v_provider.get()
        host, port, sec, note = mailer.PROVIDERS.get(name, mailer.PROVIDERS["Personnalisé"])
        if not init and name != "Personnalisé":
            self.v_host.set(host)
            self.v_port.set(str(port))
            self.v_sec.set(mailer.SECURITY_LABELS[sec])
        self.lbl_provider.config(text="ℹ " + note)

    def _test_upstream(self):
        self.save(quiet=True)
        up = self.cfg["upstream"]
        to = up["test_to"] or up["from_addr"] or up["username"]
        if not (up["host"] and to):
            return messagebox.showwarning(APP_NAME, "Renseignez le serveur et l'adresse de test.")
        self.lbl_up.config(text="Envoi en cours…", style="TLabel")
        log.info("Test d'envoi via %s:%s vers %s", up["host"], up["port"], to)

        def done(ok, res):
            if ok:
                self.lbl_up.config(text=f"✔ Message de test envoyé à {to}. Vérifiez la boîte de réception "
                                        "(et les indésirables).", style="Ok.TLabel")
                log.info("Test SMTP réussi")
            else:
                hint = ""
                txt = str(res)
                if "535" in txt or "534" in txt or "authentication" in txt.lower():
                    hint = "\n→ Identifiants refusés : utilisez un mot de passe d'application (voir le guide)."
                elif "timed out" in txt.lower() or "10060" in txt:
                    hint = "\n→ Délai dépassé : port bloqué par le réseau/antivirus ? Essayez 465 SSL ou 587 STARTTLS."
                self.lbl_up.config(text=f"✘ Échec : {txt}{hint}", style="Err.TLabel")
                log.error("Test SMTP échoué : %s", txt)
        self._run_bg(lambda: mailer.send_test(up, to), done)

    def _toggle_relay(self):
        if self.relay and self.relay.running:
            self.relay.stop()
            self.relay = None
            self._relay_ui(False)
            return
        self.save(quiet=True)
        if self.cfg["relay"]["forward_email"] and not self.cfg["upstream"]["host"]:
            return messagebox.showwarning(APP_NAME, "Configurez d'abord le serveur SMTP du fournisseur.")
        try:
            self.relay = RelayServer(self.cfg)
            self.relay.start()
        except Exception as e:
            self.relay = None
            log.error("Démarrage du relais impossible : %s", e)
            return messagebox.showerror(APP_NAME, str(e))
        self._relay_ui(True)

    def _relay_ui(self, on):
        if on:
            self.v_relay_status.set(f"En marche — {netutil.local_ip()}:{self.relay.port}")
            self.lbl_relay.config(style="Ok.TLabel")
            self.btn_relay.config(text="■ Arrêter le relais")
            self.lbl_side_relay.config(text=f"●  En marche (port {self.relay.port})", fg="#8FD9A8")
        else:
            self.v_relay_status.set("Arrêté")
            self.lbl_relay.config(style="Err.TLabel")
            self.btn_relay.config(text="▶ Démarrer le relais")
            self.lbl_side_relay.config(text="●  Arrêté", fg="#F2A097")

    def _test_relay(self):
        import smtplib
        from email.message import EmailMessage
        self.save(quiet=True)
        c = self.cfg
        to = c["upstream"]["test_to"] or c["upstream"]["from_addr"] or c["upstream"]["username"]
        if not to:
            return messagebox.showwarning(APP_NAME, "Renseignez l'adresse « Envoyer un test à ».")
        port = c["relay"]["listen_port"]

        def send():
            msg = EmailMessage()
            msg["From"] = "mfp-test@scanner.local"
            msg["To"] = to
            msg["Subject"] = "Test du relais Toshiba & Lexmark Scan Setup"
            msg.set_content("Simulation d'un scan envoyé par l'imprimante via le relais local.")
            msg.add_attachment(b"Fichier de test Toshiba & Lexmark Scan Setup\n", maintype="text", subtype="plain",
                               filename="test_scan.txt")
            with smtplib.SMTP(netutil.local_ip(), port, timeout=60) as s:
                if c["relay"]["auth_user"]:
                    s.login(c["relay"]["auth_user"], c["relay"]["auth_password"])
                s.send_message(msg)

        def done(ok, res):
            if ok:
                messagebox.showinfo(APP_NAME, f"Le relais a accepté le message de test pour {to}.\n"
                                              "Consultez le Journal pour le détail.")
            else:
                messagebox.showerror(APP_NAME, f"Le relais ne répond pas sur le port {port} :\n{res}\n\n"
                                               "Le relais est-il démarré ?")
        self._run_bg(send, done)

    def _fw_relay(self):
        self.save(quiet=True)
        self._run_bg(lambda: autostart.open_firewall_port(self.cfg["relay"]["listen_port"]),
                     lambda ok, res: messagebox.showinfo(APP_NAME, res[1] if ok else str(res)))

    def _toggle_autostart(self):
        self.save(quiet=True)
        try:
            msg = autostart.enable() if self.v_autostart.get() else autostart.disable()
            log.info(msg)
        except Exception as e:
            self.v_autostart.set(False)
            messagebox.showerror(APP_NAME, f"Impossible de configurer le démarrage automatique : {e}")

    # ------------------------------------------------------------------ 4. Fiche imprimante
    def _build_printer(self):
        f = self.pages["printer"]["inner"]
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Button(top, text="Copier", style="Accent.TButton", command=self._copy_summary).pack(side="left")
        ttk.Button(top, text="Exporter (.txt)", command=self._export_summary).pack(side="left", padx=6)
        ttk.Button(top, text="Ouvrir l'interface Web", command=self._open_rui).pack(side="left")
        mono = ("Consolas", 10) if IS_WINDOWS else ("Menlo", 12)
        box = ttk.Frame(f)
        box.pack(fill="both", expand=True, pady=(12, 0))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.txt_printer = tk.Text(box, wrap="none", font=mono, relief="flat", borderwidth=0, padx=12, pady=10,
                                   background=SOFT, foreground=TEXT, highlightthickness=1,
                                   highlightbackground=BORDER, highlightcolor=BORDER)
        ys = ttk.Scrollbar(box, orient="vertical", command=self.txt_printer.yview)
        xs = ttk.Scrollbar(box, orient="horizontal", command=self.txt_printer.xview)
        self.txt_printer.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.txt_printer.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="we")
        self._refresh_summary()

    def _refresh_summary(self):
        if hasattr(self, "txt_printer"):
            self._set_text(self.txt_printer, printer_summary.build(self._collect()))

    def _copy_summary(self):
        self.clipboard_clear()
        self.clipboard_append(self.txt_printer.get("1.0", "end"))
        log.info("Fiche de réglages copiée dans le presse-papiers")

    def _export_summary(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="Reglages_imprimante.txt",
                                         filetypes=[("Texte", "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(self.txt_printer.get("1.0", "end"))
            log.info("Fiche exportée : %s", p)

    # ------------------------------------------------------------------ 5. FILE_SHARE (Toshiba)
    def _build_fileshare(self):
        f = self.pages["fileshare"]["inner"]

        pb = self._section(f, "Le problème")
        ttk.Label(pb, wraplength=WRAP - 40, justify="left", text=(
            "Les scans « Enregistrer en tant que fichier » vers le stockage interne du copieur se récupèrent "
            "depuis le PC dans le dossier partagé FILE_SHARE du copieur. En tapant son adresse dans "
            "l'Explorateur Windows, une fenêtre peut demander un nom d'utilisateur et un mot de passe, "
            "et le dossier ne s'ouvre pas.")).pack(anchor="w")

        so = self._section(f, "La solution, dans TopAccess")
        so.columnconfigure(1, weight=1)
        steps = [
            "Ouvrez TopAccess avec le compte administrateur, puis Administration › Configuration › Réseau › SMB.",
            "Saisissez un nom d'utilisateur et un mot de passe, puis enregistrez.",
            "Désactivez ensuite cette authentification, puis enregistrez à nouveau.",
            "Rouvrez le dossier FILE_SHARE depuis ce PC : il s'ouvre sans demander d'identifiants.",
        ]
        for i, txt in enumerate(steps):
            ttk.Label(so, text=str(i + 1), style="Num.TLabel").grid(row=i, column=0, sticky="nw", padx=(0, 12), pady=5)
            ttk.Label(so, text=txt, wraplength=WRAP - 90, justify="left").grid(row=i, column=1, sticky="w", pady=5)
        ttk.Label(so, style="Muted.TLabel", wraplength=WRAP - 40, justify="left", text=(
            "Si la fenêtre persiste, saisissez dans Windows le nom d'utilisateur et le mot de passe définis à "
            "l'étape 2. Les intitulés des menus varient selon le modèle et la version du micrologiciel.")).grid(
            row=len(steps), column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(so, text="Ouvrir TopAccess", command=self._open_rui).grid(
            row=len(steps) + 1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ck = self._section(f, "Vérifier depuis ce PC")
        line = ttk.Frame(ck)
        line.pack(fill="x")
        ttk.Label(line, text="Adresse du dossier :").pack(side="left")
        ttk.Label(line, textvariable=self.v_fs_path, style="H.TLabel").pack(side="left", padx=8)
        fb = ttk.Frame(ck)
        fb.pack(fill="x", pady=(10, 0))
        ttk.Button(fb, text="Tester l'accès", style="Accent.TButton", command=self._test_fileshare).pack(side="left")
        ttk.Button(fb, text="Ouvrir FILE_SHARE", command=self._open_fileshare).pack(side="left", padx=6)
        self.lbl_fileshare = ttk.Label(ck, text="", wraplength=WRAP - 40, justify="left")
        self.lbl_fileshare.pack(anchor="w", pady=(10, 0))
        self.v_printer.trace_add("write", lambda *a: self._refresh_fileshare_path())
        self._refresh_fileshare_path()

    def _refresh_fileshare_path(self):
        ip = self.v_printer.get().strip()
        self.v_fs_path.set(f"\\\\{ip}\\{netutil.FILE_SHARE}" if ip
                           else "saisissez d'abord l'adresse IP du copieur (page Accueil)")

    def _fileshare_path(self):
        ip = self.v_printer.get().strip()
        if not ip:
            messagebox.showwarning(APP_NAME, "Saisissez l'adresse IP du copieur dans la page Accueil.")
            return None
        return ip, f"\\\\{ip}\\{netutil.FILE_SHARE}"

    def _open_fileshare(self):
        r = self._fileshare_path()
        if r:
            self.save(quiet=True)
            log.info("Ouverture de %s", r[1])
            self._open_path(r[1])

    def _test_fileshare(self):
        r = self._fileshare_path()
        if not r:
            return
        ip, path = r
        self.save(quiet=True)
        self.lbl_fileshare.config(text=f"Test de {path} en cours…", style="TLabel")
        msgs = {
            "ok": ("✔ Accès sans identifiants : {d}.", "Ok.TLabel"),
            "auth": ("✘ Le copieur demande un nom d'utilisateur et un mot de passe ({d}).\n"
                     "→ Appliquez la solution ci-dessus dans TopAccess, puis relancez le test.", "Err.TLabel"),
            "guest_blocked": ("✘ Windows refuse l'accès invité non authentifié ({d}).\n"
                              "→ Appliquez la solution ci-dessus ; sinon saisissez dans Windows le nom "
                              "d'utilisateur et le mot de passe définis dans TopAccess.", "Err.TLabel"),
            "no_smb": ("✘ Le copieur ne répond pas en SMB ({d}).\n"
                       "→ Vérifiez l'IP et que le serveur SMB est activé dans TopAccess › Réseau › SMB.", "Err.TLabel"),
            "unreachable": ("✘ Copieur introuvable sur le réseau ({d}).", "Err.TLabel"),
            "no_share": ("✘ Le partage FILE_SHARE n'existe pas sur ce copieur ({d}).", "Err.TLabel"),
            "error": ("✘ Échec : {d}", "Err.TLabel"),
        }

        def done(ok, res):
            if not ok:
                return self.lbl_fileshare.config(text=f"✘ {res}", style="Err.TLabel")
            status, detail = res
            text, style = msgs.get(status, msgs["error"])
            self.lbl_fileshare.config(text=text.replace("{d}", detail), style=style)
            (log.info if status == "ok" else log.warning)("Test FILE_SHARE %s : %s (%s)", path, status, detail)
        self._run_bg(lambda: netutil.check_unc(ip), done)

    # ------------------------------------------------------------------ Journal
    def _build_log(self):
        f = self.pages["log"]["inner"]
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="Ouvrir le fichier journal",
                   command=lambda: self._open_path(str(config.log_file()))).pack(side="left")
        ttk.Button(b, text="Renvoyer la file d'attente",
                   command=lambda: self._run_bg(lambda: mailer.process_queue(self._collect()),
                                                lambda ok, n: log.info("%s message(s) renvoyé(s)", n if ok else 0))
                   ).pack(side="left", padx=6)
        self.txt_log = ScrolledText(f, height=20, state="disabled", relief="flat", borderwidth=0, padx=12, pady=10,
                                    font=("Consolas", 10) if IS_WINDOWS else None, background=SOFT,
                                    foreground=TEXT, highlightthickness=1, highlightbackground=BORDER,
                                    highlightcolor=BORDER)
        self.txt_log.pack(fill="both", expand=True, pady=(12, 0))

    def _poll_log(self):
        try:
            while True:
                line = self.log_q.get_nowait()
                self.txt_log.config(state="normal")
                self.txt_log.insert("end", line + "\n")
                self.txt_log.see("end")
                self.txt_log.config(state="disabled")
        except queue.Empty:
            pass
        self.after(300, self._poll_log)

    def _on_close(self):
        self.save(quiet=True)
        if self.relay and self.relay.running:
            if not messagebox.askyesno(APP_NAME, "Le relais SMTP est en marche. Fermer arrête la réception des "
                                                 "scans par e-mail (sauf démarrage automatique activé).\n\nQuitter ?"):
                return
            self.relay.stop()
        self.destroy()


def run():
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = App()
    app.mainloop()
