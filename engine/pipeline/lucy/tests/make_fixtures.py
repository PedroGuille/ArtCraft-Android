"""Original synthetic files for the real-engine round-trip checks."""
from pathlib import Path
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from reportlab.pdfgen import canvas

out = Path(__file__).resolve().parents[1] / "build/qa/fixtures"
out.mkdir(parents=True, exist_ok=True)
doc = Document()
doc.add_heading("Folio integration test", 0)
doc.add_paragraph("Folio roundtrip marker 2026")
doc.save(out / "roundtrip.docx")
wb = Workbook()
ws = wb.active
ws["A1"], ws["B1"], ws["C1"], ws["A2"] = 7, 5, "=SUM(A1:B1)", "Folio roundtrip marker"
wb.save(out / "roundtrip.xlsx")
deck = Presentation()
slide = deck.slides.add_slide(deck.slide_layouts[1])
slide.shapes.title.text = "Folio roundtrip marker"
slide.placeholders[1].text = "An original integration test presentation."
deck.save(out / "roundtrip.pptx")
pdf = canvas.Canvas(str(out / "roundtrip.pdf"))
pdf.drawString(60, 760, "Folio roundtrip marker 2026")
pdf.save()
print(f"Created original fixtures in {out}")

# Multiple pages make independent scrolling in split view observable.
pdf = canvas.Canvas(str(out / "split-pages.pdf"))
for page in range(1, 7):
    pdf.setFont("Helvetica", 20)
    pdf.drawString(60, 760, f"Lucy PDF page {page}")
    for line in range(10):
        pdf.drawString(60, 700 - line * 35, f"Page {page}, paragraph {line + 1}")
    pdf.showPage()
pdf.save()
