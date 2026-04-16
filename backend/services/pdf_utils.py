# backend/services/pdf_utils.py
from io import BytesIO
from pypdf import PdfReader, PdfWriter
import fitz  # PyMuPDF

def slice_first_pages(pdf_bytes: bytes, max_pages: int = 8) -> bytes:
    """Return a new PDF that contains only the first `max_pages` pages."""
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i in range(min(max_pages, len(reader.pages))):
        writer.add_page(reader.pages[i])
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def rasterize_pdf_to_jpegs(pdf_bytes: bytes, max_pages: int = 4, dpi: int = 120) -> list[bytes]:
    ...

    """
    Render the first `max_pages` pages to images and return bytes.
    Uses JPEG if available (no quality param in PyMuPDF), otherwise PNG.
    Lower DPI to reduce payload size if Azure still complains.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = min(max_pages, len(doc))
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    imgs: list[bytes] = []
    for i in range(pages):
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        try:
            # PyMuPDF encodes JPEG at its default quality; no quality kw supported
            imgs.append(pix.tobytes("jpeg"))
        except TypeError:
            # Some builds don’t support 'jpeg' — fall back to png
            imgs.append(pix.tobytes("png"))
    doc.close()
    return imgs
