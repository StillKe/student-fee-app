from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import io

def generate_fee_pdf(data, password):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, height - 50, "AJA School - Fee Statement")

    p.setFont("Helvetica", 12)
    y = height - 100
    for key, val in data.items():
        p.drawString(50, y, f"{key.replace('_', ' ').title()}: {val}")
        y -= 20

    p.showPage()
    p.save()

    # Encrypt PDF
    buffer.seek(0)
    reader = PdfReader(buffer)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)

    protected_buffer = io.BytesIO()
    writer.write(protected_buffer)
    protected_buffer.seek(0)
    return protected_buffer
