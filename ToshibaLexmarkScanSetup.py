#!/usr/bin/env python3
"""Toshiba & Lexmark Scan Setup — point d'entrée.

  python ToshibaLexmarkScanSetup.py            interface graphique
  python ToshibaLexmarkScanSetup.py --relay    relais SMTP seul, sans interface (démarrage automatique)
"""
import logging
import logging.handlers
import signal
import sys
import threading

from tlscan import APP_NAME, VERSION, config


def _setup_logging(console: bool):
    root = logging.getLogger("tlscan")
    root.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(config.log_file(), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root.addHandler(fh)
    if console and sys.stderr:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        root.addHandler(ch)


def run_relay_headless():
    from tlscan.smtp_relay import RelayServer
    _setup_logging(console=True)
    log = logging.getLogger("tlscan")
    cfg = config.load()
    log.info("%s %s — relais SMTP en mode service", APP_NAME, VERSION)
    srv = RelayServer(cfg)
    srv.start()
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: stop.set())
        except (ValueError, OSError):
            pass
    while not stop.wait(1):
        if not srv.running:
            log.error("Le relais s'est arrêté de façon inattendue")
            sys.exit(1)
    srv.stop()


def main():
    if "--relay" in sys.argv:
        run_relay_headless()
        return
    _setup_logging(console=False)
    from tlscan import gui
    gui.run()


if __name__ == "__main__":
    main()
