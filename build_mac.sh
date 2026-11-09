#!/bin/bash
# Compile Toshiba & Lexmark Scan Setup en application macOS (dist/ToshibaLexmarkScanSetup.app)
# Usage : bash build_mac.sh   (avec le Python de python.org)
set -e
cd "$(dirname "$0")"
python3 -m pip install --upgrade pyinstaller
python3 -m PyInstaller --noconfirm --windowed --name ToshibaLexmarkScanSetup \
  --osx-bundle-identifier com.tlscansetup.app ToshibaLexmarkScanSetup.py
echo "OK : dist/ToshibaLexmarkScanSetup.app"
