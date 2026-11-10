@echo off
REM Compile Toshiba Lexmark Scan Setup en un seul fichier ToshibaLexmarkScanSetup.exe (dossier dist\)
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller || goto :err
py -3 -m PyInstaller --noconfirm --onefile --windowed --name ToshibaLexmarkScanSetup --icon assets\icon.ico --add-data "assets\icon.ico;assets" --add-data "assets\icon-256.png;assets" ToshibaLexmarkScanSetup.py || goto :err
echo.
echo  OK : dist\ToshibaLexmarkScanSetup.exe
pause
exit /b 0
:err
echo  Echec de la compilation.
pause
exit /b 1
