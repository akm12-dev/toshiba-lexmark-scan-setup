"""Mini-serveur SMTP local : reçoit les scans de l'imprimante Toshiba / Lexmark (sans TLS) et les
retransmet au fournisseur de messagerie (avec TLS + authentification) et/ou les
enregistre dans un dossier.

Implémentation 100 % bibliothèque standard (asyncio), sans dépendance externe.
Sécurité : n'accepte que les connexions du réseau local (ou des IP autorisées)
pour ne jamais devenir un relais ouvert.
"""
import asyncio
import base64
import binascii
import logging
import socket
import threading

from . import mailer, netutil

log = logging.getLogger("tlscan.relay")

MAX_SIZE = 100 * 1024 * 1024  # 100 Mo
MAX_RCPTS = 100
QUEUE_RETRY_SECONDS = 300


class _Session:
    def __init__(self, server: "RelayServer", reader, writer):
        self.srv = server
        self.r = reader
        self.w = writer
        self.peer = (writer.get_extra_info("peername") or ("?", 0))[0]
        self.authed = False
        self.reset()

    def reset(self):
        self.mail_from = None
        self.rcpts = []

    async def send(self, line: str):
        self.w.write((line + "\r\n").encode("utf-8", "replace"))
        await self.w.drain()

    async def readline(self) -> bytes:
        line = await asyncio.wait_for(self.r.readline(), timeout=300)
        if not line:
            raise ConnectionResetError
        return line

    async def run(self):
        if not netutil.ip_allowed(self.peer, self.srv.allowed):
            log.warning("Connexion refusée depuis %s (IP non autorisée)", self.peer)
            await self.send("554 5.7.1 Access denied")
            return
        log.info("Connexion de %s", self.peer)
        await self.send(f"220 {self.srv.hostname} ScanSetup Relay ESMTP")
        while True:
            raw = (await self.readline()).decode("utf-8", "replace").rstrip("\r\n")
            cmd, _, arg = raw.partition(" ")
            cmd = cmd.upper()
            handler = getattr(self, "cmd_" + cmd, None) if cmd.isalpha() else None
            if handler is None:
                await self.send("500 5.5.1 Command not recognized")
                continue
            if await handler(arg.strip()) == "quit":
                return

    # --- commandes SMTP -------------------------------------------------------
    async def cmd_HELO(self, arg):
        self.reset()
        await self.send(f"250 {self.srv.hostname}")

    async def cmd_EHLO(self, arg):
        self.reset()
        self.w.write(
            (f"250-{self.srv.hostname}\r\n250-SIZE {MAX_SIZE}\r\n250-8BITMIME\r\n"
             "250-AUTH PLAIN LOGIN\r\n250-AUTH=PLAIN LOGIN\r\n250 HELP\r\n").encode())
        await self.w.drain()

    async def cmd_AUTH(self, arg):
        parts = arg.split()
        if not parts:
            return await self.send("501 5.5.4 Syntax: AUTH mechanism")
        mech = parts[0].upper()
        try:
            if mech == "PLAIN":
                if len(parts) > 1:
                    token = parts[1]
                else:
                    await self.send("334 ")
                    token = (await self.readline()).decode().strip()
                fields = base64.b64decode(token).split(b"\0")
                user, pwd = fields[-2].decode("utf-8", "replace"), fields[-1].decode("utf-8", "replace")
            elif mech == "LOGIN":
                if len(parts) > 1:
                    user = base64.b64decode(parts[1]).decode("utf-8", "replace")
                else:
                    await self.send("334 VXNlcm5hbWU6")
                    user = base64.b64decode((await self.readline()).strip()).decode("utf-8", "replace")
                await self.send("334 UGFzc3dvcmQ6")
                pwd = base64.b64decode((await self.readline()).strip()).decode("utf-8", "replace")
            else:
                return await self.send("504 5.5.4 Unrecognized authentication type")
        except (binascii.Error, IndexError, ValueError):
            return await self.send("501 5.5.2 Cannot decode response")
        if self.srv.check_auth(user, pwd):
            self.authed = True
            await self.send("235 2.7.0 Authentication successful")
        else:
            log.warning("Échec d'authentification depuis %s (utilisateur '%s')", self.peer, user)
            await self.send("535 5.7.8 Authentication credentials invalid")

    @staticmethod
    def _addr(arg: str, keyword: str):
        if not arg.upper().startswith(keyword):
            return None
        rest = arg[len(keyword):].strip()
        if rest.startswith("<"):
            end = rest.find(">")
            return rest[1:end] if end != -1 else None
        return rest.split()[0] if rest else ""

    async def cmd_MAIL(self, arg):
        if self.srv.auth_required and not self.authed:
            return await self.send("530 5.7.0 Authentication required")
        addr = self._addr(arg, "FROM:")
        if addr is None:
            return await self.send("501 5.5.4 Syntax: MAIL FROM:<address>")
        self.reset()
        self.mail_from = addr
        await self.send("250 2.1.0 OK")

    async def cmd_RCPT(self, arg):
        if self.mail_from is None:
            return await self.send("503 5.5.1 Need MAIL command")
        addr = self._addr(arg, "TO:")
        if not addr:
            return await self.send("501 5.5.4 Syntax: RCPT TO:<address>")
        if len(self.rcpts) >= MAX_RCPTS:
            return await self.send("452 4.5.3 Too many recipients")
        self.rcpts.append(addr)
        await self.send("250 2.1.5 OK")

    async def cmd_DATA(self, arg):
        if not self.rcpts:
            return await self.send("503 5.5.1 Need RCPT command")
        await self.send("354 End data with <CR><LF>.<CR><LF>")
        chunks, size, too_big = [], 0, False
        while True:
            line = await self.readline()
            if line in (b".\r\n", b".\n"):
                break
            if line.startswith(b"."):
                line = line[1:]
            size += len(line)
            if size > MAX_SIZE:
                too_big = True
            elif not too_big:
                chunks.append(line)
        if too_big:
            self.reset()
            return await self.send("552 5.3.4 Message too big")
        data = b"".join(chunks)
        mail_from, rcpts = self.mail_from, list(self.rcpts)
        self.reset()
        loop = asyncio.get_running_loop()
        ok, info = await loop.run_in_executor(None, self.srv.deliver, self.peer, mail_from, rcpts, data)
        await self.send("250 2.0.0 OK " + info if ok else "451 4.3.0 " + info)

    async def cmd_RSET(self, arg):
        self.reset()
        await self.send("250 2.0.0 OK")

    async def cmd_NOOP(self, arg):
        await self.send("250 2.0.0 OK")

    async def cmd_VRFY(self, arg):
        await self.send("252 2.5.2 Cannot VRFY user")

    async def cmd_STARTTLS(self, arg):
        await self.send("454 4.7.0 TLS not available")

    async def cmd_HELP(self, arg):
        await self.send("214 ScanSetup relay")

    async def cmd_QUIT(self, arg):
        await self.send("221 2.0.0 Bye")
        return "quit"


class RelayServer:
    """Serveur SMTP exécuté dans un thread dédié (utilisable depuis l'interface ou en mode service)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        relay = cfg["relay"]
        self.port = int(relay["listen_port"])
        self.allowed = netutil.parse_allowed(relay.get("allowed_ips", ""))
        self.auth_user = relay.get("auth_user", "").strip()
        self.auth_password = relay.get("auth_password", "")
        self.auth_required = bool(self.auth_user)
        self.hostname = socket.gethostname()
        self._loop = None
        self._server = None
        self._thread = None
        self._started = threading.Event()
        self._error = None
        self._stop_retry = threading.Event()

    # --- logique métier --------------------------------------------------------
    def check_auth(self, user: str, pwd: str) -> bool:
        if not self.auth_required:
            return True  # l'imprimante peut envoyer des identifiants, on les accepte
        return user == self.auth_user and pwd == self.auth_password

    def deliver(self, peer: str, mail_from: str, rcpts: list, data: bytes):
        relay = self.cfg["relay"]
        log.info("Scan reçu de %s (%d Ko) pour %s", peer, len(data) // 1024, ", ".join(rcpts))
        notes = []
        if relay.get("save_attachments"):
            try:
                files = mailer.save_attachments(data, relay)
                for f in files:
                    log.info("Pièce jointe enregistrée : %s", f)
                notes.append(f"{len(files)} file(s) saved")
            except Exception as e:
                log.error("Enregistrement des pièces jointes impossible : %s", e)
                if not relay.get("forward_email"):
                    return False, "Cannot save attachments"
        if relay.get("forward_email", True):
            try:
                mailer.send_upstream(self.cfg["upstream"], relay, mail_from, rcpts, data)
                log.info("E-mail transmis via %s à %s", self.cfg["upstream"]["host"], ", ".join(rcpts))
                notes.append("relayed")
            except Exception as e:
                path = mailer.enqueue(mail_from, rcpts, data)
                log.error("Envoi impossible (%s) : message mis en file d'attente (%s), nouvel essai dans 5 min",
                          e, path.name)
                notes.append("queued")
        return True, " ".join(notes) or "accepted"

    # --- cycle de vie ----------------------------------------------------------
    async def _handle(self, reader, writer):
        try:
            await _Session(self, reader, writer).run()
        except (ConnectionResetError, asyncio.TimeoutError, asyncio.IncompleteReadError, BrokenPipeError):
            pass
        except Exception as e:
            log.exception("Erreur de session SMTP : %s", e)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._server = self._loop.run_until_complete(
                asyncio.start_server(self._handle, host=None, port=self.port, limit=1024 * 1024,
                                     reuse_address=None))
        except OSError as e:
            self._error = e
            self._started.set()
            return
        self._started.set()
        try:
            self._loop.run_forever()
        finally:
            self._server.close()
            self._loop.run_until_complete(self._server.wait_closed())
            self._loop.close()

    def _retry_loop(self):
        while not self._stop_retry.wait(QUEUE_RETRY_SECONDS):
            if mailer.queue_size():
                try:
                    mailer.process_queue(self.cfg)
                except Exception as e:
                    log.error("File d'attente : %s", e)

    def start(self):
        self._thread = threading.Thread(target=self._run, name="smtp-relay", daemon=True)
        self._thread.start()
        self._started.wait(10)
        if self._error:
            if getattr(self._error, "errno", None) in (98, 48, 10048, 10013):
                raise OSError(f"Le port {self.port} est déjà utilisé ou interdit. "
                              "Le relais tourne peut-être déjà en arrière-plan.") from self._error
            raise self._error
        threading.Thread(target=self._retry_loop, name="queue-retry", daemon=True).start()
        log.info("Relais SMTP démarré sur le port %d (IP du PC : %s)", self.port, netutil.local_ip())

    def stop(self):
        self._stop_retry.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(5)
        log.info("Relais SMTP arrêté")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
