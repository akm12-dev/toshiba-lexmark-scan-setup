"""Dessine l'icône de Toshiba & Lexmark Scan Setup (icon.ico + icon-256.png), famille d'icônes AKM12.

Carré bleu nuit arrondi, multifonction blanche avec trait de lumière bleu et feuille numérisée,
pastille sarcelle avec un dossier et une flèche (scan vers dossier / e-mail).
Usage : py assets/make_icon.py   (écrit icon.ico et icon-256.png à côté de ce script)
"""
from pathlib import Path

from PIL import Image, ImageDraw

NAV = (22, 33, 58)
BLUE = (47, 123, 235)
WHITE = (255, 255, 255)
LID = (205, 214, 226)
ACCENT = (14, 150, 135)
S = 1024

def draw(accent) -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((32, 32, S - 32, S - 32), radius=210, fill=NAV)

    # Capot du scanner (légèrement ouvert) et vitre avec trait de lumière
    d.rounded_rectangle((170, 230, 810, 320), radius=34, fill=LID)
    d.rounded_rectangle((170, 340, 810, 720), radius=70, fill=WHITE)
    d.rounded_rectangle((220, 372, 760, 404), radius=16, fill=BLUE)       # lumière de numérisation
    # Feuille numérisée qui sort
    d.rounded_rectangle((300, 610, 680, 662), radius=20, fill=NAV)
    d.rounded_rectangle((330, 640, 650, 790), radius=18, fill=WHITE)
    for y in (680, 715, 750):
        d.rounded_rectangle((365, y, 615, y + 14), radius=7, fill=LID)
    # Voyant
    d.ellipse((650, 440, 710, 500), fill=BLUE)

    # Pastille avec dossier + flèche entrante
    cx, cy, r = 745, 745, 195
    d.ellipse((cx - r - 26, cy - r - 26, cx + r + 26, cy + r + 26), fill=NAV)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
    # dossier
    fx0, fy0, fx1, fy1 = cx - 110, cy - 50, cx + 110, cy + 100
    d.rounded_rectangle((fx0, fy0 - 32, fx0 + 95, fy0 + 10), radius=14, fill=WHITE)   # onglet
    d.rounded_rectangle((fx0, fy0, fx1, fy1), radius=20, fill=WHITE)
    # flèche vers le bas, dans le dossier (couleur de la pastille)
    d.rectangle((cx - 16, cy - 20, cx + 16, cy + 30), fill=accent)
    d.polygon([(cx - 48, cy + 22), (cx + 48, cy + 22), (cx, cy + 72)], fill=accent)
    return im


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    big = draw(ACCENT).resize((256, 256), Image.LANCZOS)
    big.save(here / "icon-256.png", optimize=True)
    big.save(here / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ok")
