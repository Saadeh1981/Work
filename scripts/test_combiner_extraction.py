import json
import sys
from pathlib import Path

from backend.services.table_extractors.combiners_strings import (
    extract_combiners_strings,
    write_combiner_test_csv,
)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage:")
        print(r'python -m scripts.test_combiner_extraction "C:\path\to\di_result.json" "C:\path\to\file.pdf"')
        sys.exit(1)

    di_json_path = Path(sys.argv[1])
    pdf_path = Path(sys.argv[2])

    if not di_json_path.exists():
        print(f"DI JSON file not found: {di_json_path}")
        sys.exit(1)

    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        sys.exit(1)

    out_dir = Path("backend/data/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{pdf_path.stem}_combiner_test_output.csv"

    raw = di_json_path.read_text(encoding="utf-8", errors="replace")

    if not raw.strip():
        print(f"DI JSON file is empty: {di_json_path}")
        sys.exit(1)

    try:
        di_result = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in file: {di_json_path}")
        print(f"JSON error: {e}")
        sys.exit(1)

    if "analyzeResult" not in di_result:
        print("JSON loaded, but top-level key 'analyzeResult' was not found.")
        print(f"Top-level keys: {list(di_result.keys())[:20]}")
        sys.exit(1)

    rows = extract_combiners_strings(
        di_result=di_result,
        overrides_path=None,
        pdf_path=str(pdf_path),
        pixel_ocr_dpi=350,
    )

    write_combiner_test_csv(rows, str(out_csv))

    print(f"Extracted {len(rows)} valid combiner rows")
    print(f"CSV written to: {out_csv}")

    for row in rows[:10]:
        print(row)


if __name__ == "__main__":
    main()