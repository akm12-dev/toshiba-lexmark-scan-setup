import copy, smtplib, sys, tempfile, time, logging
from pathlib import Path
from email.message import EmailMessage
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
from tlscan import config, mailer, smtp_relay, printer_summary, netutil

tmp = Path(tempfile.mkdtemp())
config.config_dir = lambda: tmp  # isole la config
cfgB = copy.deepcopy(config.DEFAULTS)
cfgB["relay"].update(listen_port=2526, forward_email=False, save_attachments=True,
                     save_folder=str(tmp / "B"), subfolder_by_date=False)
cfgA = copy.deepcopy(config.DEFAULTS)
cfgA["upstream"].update(host="127.0.0.1", port=2526, security="none", from_addr="compte@exemple.fr")
cfgA["relay"].update(listen_port=2525, auth_user="canon", auth_password="Secr3t!", save_attachments=True,
                     save_folder=str(tmp / "A"))
B = smtp_relay.RelayServer(cfgB); B.start()
A = smtp_relay.RelayServer(cfgA); A.start()

pdf = b"%PDF-1.4\n%fake scan\n" + bytes(range(256)) * 2000
msg = EmailMessage()
msg["From"] = "imprimante@canon.local"; msg["To"] = "dest@exemple.fr"; msg["Subject"] = "Scan"
msg.set_content("Document numerise\n.ligne commencant par un point\n")
msg.add_attachment(pdf, maintype="application", subtype="pdf", filename="SCAN_0001.pdf")

# 1) sans auth -> refus
try:
    with smtplib.SMTP("127.0.0.1", 2525) as s:
        s.send_message(msg)
    print("FAIL: accepted without auth")
except smtplib.SMTPSenderRefused as e:
    print("OK auth required:", e.smtp_code)
# 2) AUTH LOGIN et PLAIN
for mech in ("LOGIN", "PLAIN"):
    with smtplib.SMTP("127.0.0.1", 2525) as s:
        s.ehlo()
        s.user, s.password = "canon", "Secr3t!"
        s.auth(mech, getattr(s, "auth_" + mech.lower()))
        s.send_message(msg)
    print("OK sent with", mech)
# 3) via IP LAN
with smtplib.SMTP(netutil.local_ip(), 2525) as s:
    s.login("canon", "Secr3t!"); s.send_message(msg)
print("OK via LAN IP", netutil.local_ip())

time.sleep(1)
a_files = list((tmp / "A").rglob("*.pdf")); b_files = list((tmp / "B").rglob("*.pdf"))
print("A saved:", len(a_files), "B saved:", len(b_files))
assert all(f.read_bytes() == pdf for f in a_files + b_files), "content mismatch"
print("Content identical OK")
# 4) upstream down -> queue
B.stop()
with smtplib.SMTP("127.0.0.1", 2525) as s:
    s.login("canon", "Secr3t!"); s.send_message(msg)
print("queued:", mailer.queue_size())
B = smtp_relay.RelayServer(cfgB); B.start()
print("resent:", mailer.process_queue(cfgA), "remaining:", mailer.queue_size())
A.stop(); B.stop()
print(printer_summary.build(cfgA)[:600])
