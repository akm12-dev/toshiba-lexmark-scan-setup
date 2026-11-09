# Régénère le guide PDF : captures d'écran -> JPEG -> PDF -> rendu des pages pour contrôle.
# Usage : powershell -ExecutionPolicy Bypass -File build_guide.ps1 [-SkipShots]
param([switch]$SkipShots)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here   # dossier docs/
$pdf  = Join-Path $root 'Guide_Toshiba_Lexmark_Scan_Setup.pdf'
$shots = Join-Path $here 'shots'
$env:PYTHONIOENCODING = 'utf-8'

if (-not $SkipShots) {
  Write-Host '1/4 Captures de l''interface (ne touchez pas la souris)...'
  py (Join-Path $here 'shots.py') $shots
  if ($LASTEXITCODE -ne 0) { throw 'Echec des captures' }
  Write-Host '2/4 Conversion PNG -> JPEG...'
  Add-Type -AssemblyName System.Drawing
  $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object MimeType -eq 'image/jpeg'
  $ep = New-Object System.Drawing.Imaging.EncoderParameters 1
  $ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, [long]93)
  Get-ChildItem (Join-Path $shots '*.png') | ForEach-Object {
    $img = [System.Drawing.Image]::FromFile($_.FullName)
    $img.Save(($_.FullName -replace '\.png$', '.jpg'), $codec, $ep); $img.Dispose()
  }
}
Write-Host '3/4 Generation du PDF...'
py (Join-Path $here 'make_pdf.py') $shots $pdf
if ($LASTEXITCODE -ne 0) { throw 'Echec de make_pdf.py' }
Write-Host '4/4 Rendu des pages pour verification (dossier pages\)...'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'render.ps1') $pdf (Join-Path $here 'pages')
Write-Host "Termine : $pdf"
Write-Host 'Pensez a verifier les numeros de page du sommaire (liste toc dans make_pdf.py).'

