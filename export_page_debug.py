from pathlib import Path
from pdf2image import convert_from_path

PDF = Path("inputs") / "SOLV Oberon Record Set Combiners.pdf"
PAGE_NUM = 69
OUT = Path("out")
OUT.mkdir(parents=True, exist_ok=True)

POPPLER_BIN = r"C:\poppler-25.12.0\Library\bin"

print("PDF exists:", PDF.exists(), str(PDF))
print("Poppler bin:", POPPLER_BIN)

try:
    pages = convert_from_path(
        str(PDF),
        dpi=300,
        first_page=PAGE_NUM,
        last_page=PAGE_NUM,
        poppler_path=POPPLER_BIN,
    )
    print("Pages returned:", len(pages))
except Exception as e:
    raise SystemExit(f"convert_from_path failed: {repr(e)}")

out_path = OUT / f"page_{PAGE_NUM}.png"
pages[0].save(out_path, "PNG")
print("Wrote:", out_path.resolve())