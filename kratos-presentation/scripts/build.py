"""Inline fonts and images into one self-contained HTML file.

usage: python3 -I scripts/build.py   (run from the kratos-presentation folder)
output: dist/Kratos_Presentation_Interactive.html
"""
import base64
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, 'src', 'index.html')
FONTS = os.path.join(HERE, 'assets', 'fonts')
IMG = os.path.join(HERE, 'assets', 'img')
OUT = os.path.join(HERE, 'dist', 'Kratos_Presentation_Interactive.html')

MIME = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2'}


def data_uri(path):
    ext = os.path.splitext(path)[1].lower()
    with open(path, 'rb') as f:
        return f'data:{MIME[ext]};base64,' + base64.b64encode(f.read()).decode()


html = open(SRC, encoding='utf-8').read()

css = open(os.path.join(FONTS, 'fonts.css'), encoding='utf-8').read()
css = re.sub(r'url\(([\w.-]+\.woff2)\)', lambda m: f'url({data_uri(os.path.join(FONTS, m.group(1)))})', css)
html = re.sub(r'<!--FONTS-->.*?<!--/FONTS-->', lambda m: f'<style id="fonts">\n{css}</style>', html, flags=re.S)

used = set()


def img(m):
    used.add(m.group(1))
    return f'url({data_uri(os.path.join(IMG, m.group(1)))})'


html = re.sub(r'url\(\.\./assets/img/([\w.-]+)\)', img, html)
assert '../assets/' not in html, 'an asset reference was not inlined'

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
unused = sorted(set(os.listdir(IMG)) - used)
print(f'{OUT}: {os.path.getsize(OUT) / 1e6:.1f} MB, {len(used)} images inlined')
if unused:
    print('unused images:', ', '.join(unused))
