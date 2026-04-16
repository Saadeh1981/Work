from pdf2image import convert_from_path
from pathlib import Path

PDF_PATH = Path(r"inputs\SOLV Oberon Record Set Combiners.pdf")
OUT_DIR = Path(r"out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# change this to the page you want (1-based)
PAGE_NUM = 1

POPPLER_BIN = Path(r"C:\poppler-25.12.0\Library\bin")

# validate poppler tools exist
pdfinfo = POPPLER_BIN / "pdfinfo.exe"
pdftoppm = POPPLER_BIN / "pdftoppm.exe"
if not pdfinfo.exists() or not pdftoppm.exists():
    raise RuntimeError(
        "Poppler not found. POPPLER_BIN must contain pdfinfo.exe and pdftoppm.exe.\n"
        f"POPPLER_BIN = {POPPLER_BIN}"
    )

pages = convert_from_path(
    str(PDF_PATH),
    dpi=300,
    first_page=PAGE_NUM,
    last_page=PAGE_NUM,
    poppler_path=str(POPPLER_BIN),
)

out_png = OUT_DIR / f"page_{PAGE_NUM}.png"
pages[0].save(out_png, "PNG")
print("Wrote:", out_png.resolve())