"""Inspect the real split-view exports, including data and formula results."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1] / "build/qa"
with ZipFile(root / "split-word.docx") as package:
    text = "".join(etree.fromstring(package.read("word/document.xml")).itertext())
    assert "Lucy split retained text" in text
with ZipFile(root / "split-sheet.xlsx") as package:
    sheet = etree.fromstring(package.read("xl/worksheets/sheet1.xml"))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    assert sheet.xpath('string(//s:c[@r="A1"]/s:v)', namespaces=ns) == "42"
    assert float(sheet.xpath('string(//s:c[@r="C1"]/s:v)', namespaces=ns)) == 47
with ZipFile(root / "split-deck.pptx") as package:
    slide = etree.fromstring(package.read("ppt/slides/slide1.xml"))
    assert "Folio roundtrip marker" in "".join(slide.itertext())
pdf = PdfReader(root / "split-pdf.pdf")
assert len(pdf.pages) == 6
assert "Lucy PDF page 6" in pdf.pages[5].extract_text()
print("PASS: split-view DOCX edit; spreadsheet A1=42 and formula=47; PPTX content; six-page PDF text.")
