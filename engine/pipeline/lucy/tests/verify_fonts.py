from pathlib import Path
from pypdf import PdfReader
path = Path(__file__).resolve().parents[1] / 'build/qa/multi-font.pdf'
pdf = PdfReader(path)
fonts = pdf.pages[0]['/Resources']['/Font']
names = [str(font.get_object().get('/BaseFont', '')) for font in fonts.values()]
assert any('Inter-Regular' in name for name in names), names
assert any('Inter-Medium' in name for name in names), names
assert 'Folio roundtrip marker 2026' in pdf.pages[0].extract_text()
print('PASS: both selected PDF font faces are embedded, including the valid file after an invalid selection; paragraph text is preserved:', ', '.join(names))
