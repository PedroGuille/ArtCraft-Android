from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1] / "build/qa"
with ZipFile(root / "undo-wordcraft.docx") as z:
    assert "Folio edited text" not in z.read("word/document.xml").decode(), "Menu Undo must change the document"
with ZipFile(root / "exported-wordcraft.docx") as z:
    xml = z.read("word/document.xml").decode()
    assert "Folio roundtrip marker 2026 Folio edited text" in xml
    assert "Dark view edit" in xml, "Typing while viewing dark pages must edit the actual DOCX"
with ZipFile(root / "exported-gridcraft.xlsx") as z:
    xml = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    formula = xml.find(".//s:c[@r='C1']", ns)
    assert formula.find("s:f", ns).text == "SUM(A1:B1)"
    assert formula.find("s:v", ns).text == "12"
with ZipFile(root / "exported-deckcraft.pptx") as z:
    assert "ppt/presentation.xml" in z.namelist(), "A PPTX must be actual OOXML, not renamed .deckcraft"
    assert b"Folio roundtrip marker" in z.read("ppt/slides/slide1.xml")
pdf = PdfReader(root / "exported-pdfcraft.pdf")
text = pdf.pages[0].extract_text()
assert "Folio roundtrip marker 2026" in text
assert "Folio PDF edited" in text
with ZipFile(root / "new-workbook.xlsx") as z:
    xml = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    assert xml.find(".//s:c[@r='A1']/s:v", ns).text == "42"
print("PASS: DOCX edits, XLSX formula and cached result, valid PPTX, editable PDF text, new spreadsheet value")

# Changing a view palette must not change saved document colours or content.
for engine, ext, members in [
    ("wordcraft", "docx", ["word/document.xml", "word/styles.xml"]),
    ("gridcraft", "xlsx", ["xl/styles.xml", "xl/worksheets/sheet1.xml"]),
    ("deckcraft", "pptx", ["ppt/slides/slide1.xml", "ppt/theme/theme1.xml"]),
]:
    with ZipFile(root / f"exported-{engine}.{ext}") as dark, ZipFile(root / f"light-export-{engine}.{ext}") as light:
        for member in members:
            assert ET.canonicalize(dark.read(member)) == ET.canonicalize(light.read(member)), (engine, member, "Display mode changed exported content")
light_pdf = PdfReader(root / "light-export-pdfcraft.pdf")
assert light_pdf.pages[0].extract_text() == text
assert light_pdf.pages[0].get_contents().get_data() == pdf.pages[0].get_contents().get_data(), "PDF display colours must not alter page paints"
print("PASS: toggling dark mode preserves exported content and colours in all four formats")
