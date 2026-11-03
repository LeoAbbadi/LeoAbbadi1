"""Crop, resize and compress the source images used by the presentation.

usage: python3 -I scripts/prep_images.py <source_root> <menu_screenshot> <out_dir>

<source_root> holds clones of public fan-site repositories (see README for the list).
"""
import sys, os
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance

SRC, MENU, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)

def p(*parts):
    return os.path.join(SRC, *parts)

G = ('Gabiel001_god_of_war_3', 'img')
C = ('CarlosAugustoPrado_God-of-War-Ragnarok', 'img')
S = ('Samuel0422_Kratos',)
E = ('Eric081a_GodOfWar', 'imgs')

def cover(im, w, h, cx=0.5, cy=0.5):
    """Scale + crop to exactly w x h, keeping the focus point (cx, cy) in frame."""
    sw, sh = im.size
    s = max(w / sw, h / sh)
    im = im.resize((round(sw * s), round(sh * s)), Image.LANCZOS)
    sw, sh = im.size
    x = min(max(round(sw * cx - w / 2), 0), sw - w)
    y = min(max(round(sh * cy - h / 2), 0), sh - h)
    return im.crop((x, y, x + w, y + h))

def save_jpg(im, name, q=80):
    im.convert('RGB').save(os.path.join(OUT, name), quality=q, optimize=True, progressive=True)

def save_webp(im, name, q=82):
    im.save(os.path.join(OUT, name), 'WEBP', quality=q, method=6)

def load(*parts):
    return Image.open(p(*parts))

# --- main menu: the player's own screenshot, with the original logo/menu blurred away
m = Image.open(MENU).convert('RGB').resize((1920, 1080), Image.LANCZOS)
blurred = m.filter(ImageFilter.GaussianBlur(38))
blurred = ImageEnhance.Brightness(blurred).enhance(0.55)
mask = Image.new('L', m.size, 0)
d = ImageDraw.Draw(mask)
for x in range(1920):
    a = 255 if x < 880 else max(0, 255 - (x - 880) * 255 // 260)
    d.line([(x, 0), (x, 1079)], fill=a)
m = Image.composite(blurred, m, mask)
save_jpg(m, 'menu.jpg', 82)

# --- backgrounds (1920x1080)
bgs = {
    'eye.jpg': (load(*E, 'UXEil8SSYdE1mzQVnoqfu3Tw.webp').crop((150, 820, 2880, 2160)), 0.5, 0.45),
    'greek.jpg': (load(*G, 'capa-home.jpeg'), 0.5, 0.5),
    'ares.jpg': (load(*G, 'kratos_ares.png').convert('RGB'), 0.5, 0.5),
    'throne.jpg': (load(*G, 'god1.webp'), 0.5, 0.5),
    'wings.jpg': (load(*G, 'god-of-war-3-01.jpg'), 0.5, 0.4),
    'zeus_fight.jpg': (load(*G, 'ktato_zeus.jpg'), 0.5, 0.5),
    'blades_floor.jpg': (load(*S, 'armas', 'del-caos-nordica.jpeg'), 0.5, 0.5),
    'boat.jpg': (load(*S, 'carrucel', '2018.jpg'), 0.5, 0.5),
    'ragnarok.jpg': (load(*G, 'ragnarok.webp'), 0.5, 0.5),
    'freya_fight.jpg': (load(*C, 'bg-hero-1920.jpg'), 0.5, 0.5),
    'hug.jpg': (load(*G, 'final.jpg'), 0.5, 0.45),
    'allies.jpg': (load(*G, 'aliados.jpg'), 0.5, 0.5),
}
for name, (im, cx, cy) in bgs.items():
    save_jpg(cover(im.convert('RGB'), 1920, 1080, cx, cy), name, 78)

# --- landscape stills for panels (960x540)
stills = {
    'pandora.jpg': (load(*G, 'Kratos_pandora.JPG'), 0.5, 0.5),
    'baldur_fight.jpg': (load(*G, 'baldor_2018.webp'), 0.5, 0.4),
    'mimir.jpg': (load(*G, 'mirmi.jpg'), 0.45, 0.5),
    'ashes.jpg': (load(*G, 'cinzas_2018.jpg'), 0.5, 0.5),
    'odin_thor.jpg': (load(*G, 'odim_thor.jpg'), 0.5, 0.5),
    'olympus_blade.jpg': (load(*S, 'armas', 'hoja-del-olimpo.jpg'), 0.5, 0.5),
    'blades.jpg': (load(*S, 'armas', 'espadas-del-caos.jpg'), 0.5, 0.5),
    'shield.jpg': (load(*S, 'armas', 'escudo.jpeg'), 0.55, 0.5),
    'axe.jpg': (load(*S, 'armas', 'leviatan.png').convert('RGBA'), 0.5, 0.5),
}
for name, (im, cx, cy) in stills.items():
    if im.mode == 'RGBA':
        bg = Image.new('RGBA', im.size, (8, 14, 22, 255)); bg.alpha_composite(im); im = bg
    save_jpg(cover(im.convert('RGB'), 960, 540, cx, cy), name, 80)

# --- portrait cards (480x640)
cards = {
    'poseidon.jpg': (load(*S, 'PJ', 'poseidon.jpg'), 0.5, 0.4),
    'hades.jpg': (load(*S, 'PJ', 'hades.jpg'), 0.5, 0.4),
    'hermes.jpg': (load(*S, 'PJ', 'hermes.jpg'), 0.6, 0.3),
    'hercules.jpg': (load(*S, 'PJ', 'hercules.jpg'), 0.5, 0.4),
    'zeus.jpg': (load(*S, 'PJ', 'zeus.webp'), 0.5, 0.35),
    'atreus.jpg': (load(*C, 'atreus.jpg'), 0.5, 0.5),
    'freya.jpg': (load(*C, 'freya.jpg'), 0.5, 0.5),
    'mimir_p.jpg': (load(*C, 'mimir.jpg'), 0.5, 0.5),
    'thor.jpg': (load(*C, 'thor.jpg'), 0.5, 0.5),
    'odin.jpg': (load(*S, 'PJ', 'odin.webp'), 0.5, 0.4),
    'baldur.jpg': (load(*S, 'PJ', 'baldur.webp'), 0.42, 0.4),
}
for name, (im, cx, cy) in cards.items():
    save_jpg(cover(im.convert('RGB'), 480, 640, cx, cy), name, 80)

# --- game covers for the chapter select (360x480)
covers = {
    'cover1.jpg': (load(*E, 'quadro-decorativo-god-of-war-1-com-moldura-a3-placa-decorativa.webp').crop((40, 40, 829, 1160)), 0.5, 0.5),
    'cover2.jpg': (load(*E, 'God_of_War_2_capa.png'), 0.5, 0.5),
    'cover3.jpg': (load(*E, 'UXEil8SSYdE1mzQVnoqfu3Tw.webp'), 0.55, 0.5),
    'cover4.jpg': (load('Eric081a_GodOfWar', 'God_of_War_2018_capa.png'), 0.5, 0.5),
    'cover5.jpg': (load(*E, 'God_of_War_Ragnarök_capa.jpg'), 0.5, 0.5),
}
for name, (im, cx, cy) in covers.items():
    save_jpg(cover(im.convert('RGB'), 360, 480, cx, cy), name, 82)

# --- cut-outs with transparency
g = load(*S, 'PJ', 'kratos-enc.png').convert('RGBA'); g.thumbnail((760, 760), Image.LANCZOS)
save_webp(g, 'greek_cutout.webp')
n = load(*C, 'kratos-atreus-1920.png').convert('RGBA'); n.thumbnail((760, 760), Image.LANCZOS)
save_webp(n, 'norse_duo.webp')

for f in sorted(os.listdir(OUT)):
    print(f, Image.open(os.path.join(OUT, f)).size, os.path.getsize(os.path.join(OUT, f)) // 1024, 'KB')
