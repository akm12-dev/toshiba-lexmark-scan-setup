#!/bin/bash
# Double-cliquez sur ce fichier (la 1re fois : clic droit > Ouvrir).
cd "$(dirname "$0")" || exit 1
PY=""
for c in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import tkinter" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3 (avec Tkinter) est requis : installez-le depuis https://www.python.org/downloads/macos/"
  open "https://www.python.org/downloads/macos/"
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi
exec "$PY" ToshibaLexmarkScanSetup.py
