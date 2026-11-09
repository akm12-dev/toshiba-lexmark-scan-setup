import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tlscan import sharing, config, autostart
out = Path(sys.argv[1])
s = copy.deepcopy(config.DEFAULTS["share"]); s["password"] = "Ab1-x'y!z"
cap = {}
def fake_ps(body):
    cap.setdefault("ps", []).append(body); return True, ""
def fake_sh(body):
    cap.setdefault("sh", []).append(body); return True, ""
sharing._run_elevated_ps = fake_ps; sharing._run_elevated_sh = fake_sh
sharing._windows_create(s); sharing._windows_remove(s, True); autostart.open_firewall_port(25)
s["folder"] = "/Users/Shared/Scans"
sharing._mac_create(s); sharing._mac_remove(s, True)
for i, b in enumerate(cap["ps"]):
    (out / f"t{i}.ps1").write_text(b, encoding="utf-8-sig")
for i, b in enumerate(cap["sh"]):
    (out / f"t{i}.sh").write_text("#!/bin/bash\n" + b, encoding="utf-8", newline="\n")
print(cap["ps"][0][:400])
