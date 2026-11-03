"""Download the latin + runic subsets listed in a Google Fonts CSS file and write a local fonts.css."""
import re, sys, os, urllib.request
src, outdir = sys.argv[1], sys.argv[2]
css = open(src).read()
blocks = re.findall(r'/\* ([\w-]+) \*/\s*@font-face \{(.*?)\}', css, re.S)
out = []
for subset, body in blocks:
    fam = re.search(r"font-family: '([^']+)'", body).group(1)
    if subset not in ('latin', 'runic'):
        continue
    if fam == 'Noto Sans Runic' and subset != 'runic':
        continue
    style = re.search(r'font-style: (\w+)', body).group(1)
    weight = re.search(r'font-weight: (\d+)', body).group(1)
    url = re.search(r'url\((https://[^)]+)\)', body).group(1)
    name = f"{fam.replace(' ', '')}-{weight}{'i' if style == 'italic' else ''}.woff2"
    urllib.request.urlretrieve(url, os.path.join(outdir, name))
    rng = re.search(r'unicode-range: ([^;]+);', body).group(1)
    out.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};font-display:block;src:url(../assets/fonts/{name}) format('woff2');unicode-range:{rng};}}")
    print(name, os.path.getsize(os.path.join(outdir, name)))
open(os.path.join(outdir, 'fonts.css'), 'w').write('\n'.join(out) + '\n')
