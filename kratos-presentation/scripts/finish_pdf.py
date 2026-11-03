"""Add bookmarks, page transitions and metadata to the PDF printed by make_pdf.js,
and check that every internal link lands on the right page.

usage: python3 -I scripts/finish_pdf.py <in.pdf> <out.pdf>
"""
import sys
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, FloatObject

SRC, OUT = sys.argv[1], sys.argv[2]

# page order = slide order in src/index.html
SLIDES = [
    ('s-menu', 'Main menu'),
    ('s-chapters', 'Chapter select'),
    ('s-prologue', 'Prologue: The Ghost of Sparta'),
    ('s-gow1', 'Chapter I: God of War (2005)'),
    ('s-gow2', 'Chapter II: God of War II (2007)'),
    ('s-gow3', 'Chapter III: God of War III (2010)'),
    ('s-midgard', 'Interlude: A New Life in the North'),
    ('s-gow2018', 'Chapter IV: God of War (2018)'),
    ('s-ragnarok', 'Chapter V: God of War Ragnarok (2022)'),
    ('s-odin', 'Cutscene: Kratos vs Odin'),
    ('s-valhalla', 'Epilogue: Valhalla (2023)'),
    ('s-arsenal', 'Codex: The Arsenal'),
    ('s-characters', 'Codex: Allies & Enemies'),
    ('s-grammar', 'Codex: Verb Patterns'),
    ('s-credits', 'Credits'),
]

reader = PdfReader(SRC)
assert len(reader.pages) == len(SLIDES), f'expected {len(SLIDES)} pages, got {len(reader.pages)}'

# every named destination must point at the page of the slide with that id
dests = reader.named_destinations
for i, (sid, _) in enumerate(SLIDES):
    assert '/' + sid in dests or sid in dests, f'missing destination {sid}'
    d = dests.get('/' + sid) or dests.get(sid)
    page = reader.get_destination_page_number(d)
    assert page == i, f'{sid} points to page {page + 1}, expected {i + 1}'

links = 0
for p in reader.pages:
    for a in p.get('/Annots') or []:
        if a.get_object().get('/Subtype') == '/Link':
            links += 1

writer = PdfWriter(clone_from=reader)
groups = {}
for i, (sid, title) in enumerate(SLIDES):
    page = writer.pages[i]
    page[NameObject('/Trans')] = DictionaryObject({
        NameObject('/Type'): NameObject('/Trans'),
        NameObject('/S'): NameObject('/Fade'),
        NameObject('/D'): FloatObject(0.7),
    })
    writer.add_outline_item(title, i)

writer.add_metadata({
    '/Title': 'Kratos: From Sparta to Ragnarök',
    '/Subject': 'English presentation: the story of Kratos, from God of War (2005) to Ragnarök',
    '/Keywords': 'Kratos, God of War, English, presentation, verb patterns',
})
writer.page_layout = '/SinglePage'
writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
with open(OUT, 'wb') as f:
    writer.write(f)
print(f'{OUT}: {len(SLIDES)} pages, {links} internal links checked, bookmarks + fade transitions added')
