"""Interface graphique (tkinter) de Toshiba & Lexmark Scan Setup."""
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

ACCENT = "#0B5C7A"  # bleu pétrole neutre


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
    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        self.relay = None
        self.log_q = queue.Queue()
        h = _QueueHandler(self.log_q)
        h.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        logging.getLogger("tlscan").addHandler(h)

        self.title(f"{APP_NAME} {VERSION}")
        self.geometry("960x860")
        self.minsize(820, 620)
        self._style()
        self._vars()
        self._build()
        self.after(200, self._poll_log)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ style
    def _style(self):
        st = ttk.Style(self)
        if "vista" in st.theme_names():
            st.theme_use("vista")
        elif "aqua" in st.theme_names():
            st.theme_use("aqua")
        else:
            st.theme_use("clam")
        base = ("Segoe UI", 10) if IS_WINDOWS else ("Helvetica Neue", 13) if IS_MAC else ("DejaVu Sans", 10)
        from tkinter import font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=base[0], size=base[1])
            except tk.TclError:
                pass
        st.configure("TNotebook.Tab", padding=(14, 6))
        st.configure("Title.TLabel", font=(base[0], base[1] + 6, "bold"))
        st.configure("H.TLabel", font=(base[0], base[1] + 1, "bold"))
        st.configure("Muted.TLabel", foreground="#666")
        st.configure("Ok.TLabel", foreground="#1a7f37")
        st.configure("Err.TLabel", foreground="#b42318")
        st.configure("Accent.TButton", font=(base[0], base[1], "bold"))
        self.base_font = base

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

    # ------------------------------------------------------------------ construction
    def _build(self):
        header = tk.Frame(self, bg=ACCENT, height=54)
        header.pack(fill="x")
        tk.Label(header, text=APP_NAME, bg=ACCENT, fg="white",
                 font=(self.base_font[0], self.base_font[1] + 7, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(header, text="Scan vers dossier  •  Scan vers e-mail",
                 bg=ACCENT, fg="#d6eef7").pack(side="left", pady=10)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        self.tab_home = self._page("1. Accueil")
        self.tab_folder = self._page("2. Scan vers dossier")
        self.tab_mail = self._page("3. Scan vers e-mail")
        self.tab_printer = self._page("4. Réglages imprimante")
        self.tab_log = self._page("Journal")
        self._build_home()
        self._build_folder()
        self._build_mail()
        self._build_printer()
        self._build_log()

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=8)
        ttk.Label(bar, text=f"Configuration : {config.config_path()}", style="Muted.TLabel").pack(side="left")
        ttk.Button(bar, text="Enregistrer", command=self.save).pack(side="right")

    def _page(self, title):
        f = ttk.Frame(self.nb, padding=16)
        self.nb.add(f, text=title)
        return f

    @staticmethod
    def _row(parent, r, label, widget, hint=None):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
        widget.grid(row=r, column=1, sticky="we", pady=3)
        if hint:
            ttk.Label(parent, text=hint, style="Muted.TLabel").grid(row=r, column=2, sticky="w", padx=8)

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
        f = self.tab_home
        ttk.Label(f, text="Bienvenue", style="Title.TLabel").pack(anchor="w")
        ttk.Label(f, wraplength=880, justify="left", text=(
            "Ce logiciel prépare votre ordinateur pour recevoir les numérisations d'un multifonction "
            "Toshiba (e-STUDIO, interface TopAccess) ou Lexmark (CX, MX, XC, XM, MB, MC…) :\n"
            "  • Scan vers dossier : crée un dossier partagé (SMB) et un compte dédié, ouvre le pare-feu.\n"
            "  • Scan vers e-mail : teste votre messagerie et, si besoin, fait office de relais SMTP pour les "
            "imprimantes qui ne gèrent pas le chiffrement moderne (Gmail, Microsoft…).\n"
            "  • Génère la fiche exacte des réglages à saisir dans l'interface Web de l'imprimante.")
                  ).pack(anchor="w", pady=(6, 14))

        box = ttk.LabelFrame(f, text="Ce PC", padding=12)
        box.pack(fill="x")
        osname = "Windows" if IS_WINDOWS else "macOS" if IS_MAC else sys.platform
        info = [("Système", osname), ("Nom du PC", netutil.hostname()), ("Adresse IP locale", netutil.local_ip())]
        for i, (k, v) in enumerate(info):
            ttk.Label(box, text=k).grid(row=i, column=0, sticky="w", padx=(0, 20))
            ttk.Label(box, text=v, style="H.TLabel").grid(row=i, column=1, sticky="w")

        box2 = ttk.LabelFrame(f, text="Imprimante", padding=12)
        box2.pack(fill="x", pady=12)
        box2.columnconfigure(1, weight=1)
        bf = ttk.Frame(box2)
        for key, label in BRANDS.items():
            ttk.Radiobutton(bf, text=label, value=key, variable=self.v_brand,
                            command=self._refresh_summary).pack(side="left", padx=(0, 18))
        bf.grid(row=0, column=1, columnspan=2, sticky="w", pady=3)
        ttk.Label(box2, text="Marque").grid(row=0, column=0, sticky="w", pady=3, padx=(0, 10))
        e = ttk.Entry(box2, textvariable=self.v_printer, width=22)
        self._row(box2, 1, "Adresse IP de l'imprimante", e,
                  "affichée sur l'écran d'accueil ou la page de config. réseau")
        btns = ttk.Frame(box2)
        btns.grid(row=2, column=1, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(btns, text="Tester la connexion", command=self._test_printer).pack(side="left")
        ttk.Button(btns, text="Ouvrir l'interface Web (TopAccess / EWS)", command=self._open_rui).pack(side="left", padx=8)
        self.lbl_printer = ttk.Label(box2, text="")
        self.lbl_printer.grid(row=3, column=1, columnspan=2, sticky="w", pady=(6, 0))

        steps = ttk.LabelFrame(f, text="Marche à suivre", padding=12)
        steps.pack(fill="x")
        ttk.Label(steps, justify="left", text=(
            "1. Choisissez la marque, saisissez l'IP de l'imprimante et testez la connexion.\n"
            "2. Onglet « Scan vers dossier » : cliquez sur « Créer le partage ».\n"
            "3. Onglet « Scan vers e-mail » : choisissez votre fournisseur, testez, démarrez le relais.\n"
            "4. Onglet « Réglages imprimante » : recopiez les valeurs dans TopAccess (Toshiba) ou l'EWS (Lexmark).")
                  ).pack(anchor="w")

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
        if ip:
            webbrowser.open(f"http://{ip}/")

    # ------------------------------------------------------------------ 2. Dossier
    def _build_folder(self):
        f = self.tab_folder
        ttk.Label(f, text="Scan vers dossier partagé (SMB)", style="Title.TLabel").pack(anchor="w")
        ttk.Label(f, wraplength=800, style="Muted.TLabel", text=(
            "L'imprimante dépose les fichiers numérisés dans un dossier partagé de ce PC, avec un compte "
            "dédié. Des droits administrateur seront demandés.")).pack(anchor="w", pady=(4, 10))

        g = ttk.LabelFrame(f, text="Paramètres du partage", padding=12)
        g.pack(fill="x")
        g.columnconfigure(1, weight=1)
        fr = ttk.Frame(g)
        ttk.Entry(fr, textvariable=self.v_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(fr, text="Parcourir…", command=lambda: self._browse(self.v_folder)).pack(side="left", padx=(6, 0))
        self._row(g, 0, "Dossier de réception", fr)
        self._row(g, 1, "Nom du partage", ttk.Entry(g, textvariable=self.v_share, width=20), "sans espace, ex : SCANS")
        self._row(g, 2, "Compte utilisateur", ttk.Entry(g, textvariable=self.v_user, width=20), "ex : scanner")
        pf = ttk.Frame(g)
        ttk.Entry(pf, textvariable=self.v_pass, width=24).pack(side="left")
        ttk.Button(pf, text="Générer", command=lambda: self.v_pass.set(_gen_password())).pack(side="left", padx=6)
        self._row(g, 3, "Mot de passe", pf, "8 caractères min., sans guillemets")

        o = ttk.LabelFrame(f, text="Options", padding=12)
        o.pack(fill="x", pady=10)
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

        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="Créer le partage", style="Accent.TButton", command=self._create_share).pack(side="left")
        ttk.Button(b, text="Vérifier", command=self._check_share).pack(side="left", padx=6)
        ttk.Button(b, text="Ouvrir le dossier", command=lambda: self._open_path(self.v_folder.get())).pack(side="left")
        ttk.Button(b, text="Supprimer le partage", command=self._remove_share).pack(side="right")

        self.txt_share = tk.Text(f, height=8, wrap="word", relief="solid", borderwidth=1, font=self.base_font,
                                 padx=6, pady=4)
        self.txt_share.pack(fill="both", expand=True, pady=(10, 0))
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
                out += (f"\n\n✔ TERMINÉ. Sur l'imprimante, créez la destination réseau (voir onglet 4) :\n"
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
        outer = self.tab_mail
        canvas = self.mail_canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        f = ttk.Frame(canvas)
        f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=f, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / (1 if IS_MAC else 120)), "units")
                        if self.nb.index("current") == 2 else None)
        try:
            bg = ttk.Style().lookup("TFrame", "background")
            canvas.configure(background=bg)
        except tk.TclError:
            pass

        ttk.Label(f, text="Scan vers e-mail (SMTP)", style="Title.TLabel").pack(anchor="w")

        m = ttk.LabelFrame(f, text="Mode d'envoi", padding=10)
        m.pack(fill="x", pady=(8, 0))
        ttk.Radiobutton(m, text="Relais via ce PC (recommandé) : imprimante → ce PC (sans TLS) → fournisseur (TLS)",
                        value="relay", variable=self.v_mode, command=self._refresh_summary).pack(anchor="w")
        ttk.Radiobutton(m, text="Direct : l'imprimante contacte elle-même le serveur du fournisseur "
                                "(modèles récents compatibles TLS 1.2)",
                        value="direct", variable=self.v_mode, command=self._refresh_summary).pack(anchor="w")

        u = ttk.LabelFrame(f, text="Compte de messagerie (serveur SMTP du fournisseur)", padding=10)
        u.pack(fill="x", pady=8)
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
        hp.grid(row=1, column=1, columnspan=2, sticky="we", pady=3)
        ttk.Label(u, text="Serveur SMTP").grid(row=1, column=0, sticky="w", pady=3, padx=(0, 10))
        self._row(u, 2, "Identifiant", ttk.Entry(u, textvariable=self.v_uuser), "souvent l'adresse e-mail complète")
        self._row(u, 3, "Mot de passe", ttk.Entry(u, textvariable=self.v_upass, show="•"), "mot de passe d'application")
        self._row(u, 4, "Adresse d'expédition", ttk.Entry(u, textvariable=self.v_from), "vide = identifiant")
        self.lbl_provider = ttk.Label(u, text="", style="Muted.TLabel", wraplength=700, justify="left")
        self.lbl_provider.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._on_provider(init=True)
        t = ttk.Frame(u)
        t.grid(row=6, column=0, columnspan=3, sticky="we", pady=(8, 0))
        ttk.Label(t, text="Envoyer un test à :").pack(side="left")
        ttk.Entry(t, textvariable=self.v_test_to, width=30).pack(side="left", padx=6)
        ttk.Button(t, text="Tester l'envoi", command=self._test_upstream).pack(side="left")
        self.lbl_up = ttk.Label(u, text="", wraplength=760, justify="left")
        self.lbl_up.grid(row=7, column=0, columnspan=3, sticky="w", pady=(4, 0))

        r = ttk.LabelFrame(f, text="Relais SMTP local (mode « Relais via ce PC »)", padding=10)
        r.pack(fill="x")
        r.columnconfigure(1, weight=1)
        self._row(r, 0, "Port d'écoute", ttk.Entry(r, textvariable=self.v_lport, width=8),
                  "25 = standard (sinon 2525 si réglable)")
        self._row(r, 1, "IP autorisées", ttk.Entry(r, textvariable=self.v_allowed),
                  "vide = tout le réseau local")
        au = ttk.Frame(r)
        ttk.Entry(au, textvariable=self.v_rauth_user, width=16).pack(side="left")
        ttk.Label(au, text="  Mot de passe").pack(side="left")
        ttk.Entry(au, textvariable=self.v_rauth_pass, width=16).pack(side="left", padx=4)
        ttk.Label(au, text="  vide = aucune", style="Muted.TLabel").pack(side="left")
        ttk.Label(r, text="Auth. (facultatif)").grid(row=2, column=0, sticky="w", pady=3, padx=(0, 10))
        au.grid(row=2, column=1, columnspan=2, sticky="w", pady=3)
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
        ttk.Checkbutton(sf, text="sous-dossier par date", variable=self.v_by_date).pack(side="left")
        self._row(r, 4, "Dossier des pièces jointes", sf)

        ctl = ttk.Frame(r)
        ctl.grid(row=5, column=0, columnspan=3, sticky="we", pady=(10, 0))
        self.btn_relay = ttk.Button(ctl, text="▶ Démarrer le relais", style="Accent.TButton", command=self._toggle_relay)
        self.btn_relay.pack(side="left")
        ttk.Button(ctl, text="Tester le relais", command=self._test_relay).pack(side="left", padx=6)
        if IS_WINDOWS:
            ttk.Button(ctl, text="Autoriser dans le pare-feu", command=self._fw_relay).pack(side="left")
        ttk.Label(ctl, text="   État :").pack(side="left")
        self.lbl_relay = ttk.Label(ctl, textvariable=self.v_relay_status, style="Err.TLabel")
        self.lbl_relay.pack(side="left")
        ttk.Checkbutton(r, text="Lancer le relais automatiquement à l'ouverture de session (en arrière-plan)",
                        variable=self.v_autostart, command=self._toggle_autostart).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        q = mailer.queue_size()
        if q:
            ttk.Label(r, text=f"{q} message(s) en attente d'envoi", style="Err.TLabel").grid(row=7, column=0, sticky="w")

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
        else:
            self.v_relay_status.set("Arrêté")
            self.lbl_relay.config(style="Err.TLabel")
            self.btn_relay.config(text="▶ Démarrer le relais")

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
                                              "Consultez l'onglet Journal pour le détail.")
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
        f = self.tab_printer
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Réglages à saisir sur l'imprimante", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Exporter (.txt)", command=self._export_summary).pack(side="right")
        ttk.Button(top, text="Copier", command=self._copy_summary).pack(side="right", padx=6)
        ttk.Button(top, text="Ouvrir l'interface Web", command=self._open_rui).pack(side="right")
        mono = ("Consolas", 10) if IS_WINDOWS else ("Menlo", 12)
        self.txt_printer = tk.Text(f, wrap="none", font=mono, relief="solid", borderwidth=1)
        self.txt_printer.pack(fill="both", expand=True, pady=(10, 0))
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._refresh_summary())
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

    # ------------------------------------------------------------------ Journal
    def _build_log(self):
        f = self.tab_log
        self.txt_log = ScrolledText(f, height=20, state="disabled", font=("Consolas", 10) if IS_WINDOWS else None)
        self.txt_log.pack(fill="both", expand=True)
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(8, 0))
        ttk.Button(b, text="Ouvrir le fichier journal", command=lambda: self._open_path(str(config.log_file()))).pack(side="left")
        ttk.Button(b, text="Renvoyer la file d'attente",
                   command=lambda: self._run_bg(lambda: mailer.process_queue(self._collect()),
                                                lambda ok, n: log.info("%s message(s) renvoyé(s)", n if ok else 0))
                   ).pack(side="left", padx=6)

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
