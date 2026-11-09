@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (start "" pyw -3 "ToshibaLexmarkScanSetup.py" & exit /b)
where pythonw >nul 2>nul && (start "" pythonw "ToshibaLexmarkScanSetup.py" & exit /b)
echo.
echo  Python 3 n'est pas installe sur ce PC.
echo  Telechargez-le sur https://www.python.org/downloads/
echo  (cochez "Add python.exe to PATH" pendant l'installation), puis relancez ce fichier.
echo.
start "" https://www.python.org/downloads/
pause
