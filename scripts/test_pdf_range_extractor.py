from __future__ import annotations

import sys
from pathlib import Path

from backend.services.pdf_range_extractor import extract_pdf_page_range


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: python -m scripts.test_pdf_range_extractor <pdf_path> <start_page> <end_page>")
        return

    path = Path(sys.argv[1])
    start_page = int(sys.argv[2])
    end_page = int(sys.argv[3])

    result = extract_pdf_page_range(str(path), start_page, end_page)

    print(f"status = {result['status']}")
    print(f"start_page = {result.get('start_page')}")
    print(f"end_page = {result.get('end_page')}")
    print(f"text_len = {result.get('text_len', 0)}")
    print(f"page_count = {len(result.get('pages', []))}")

    if result.get("pages"):
        print("\nFirst pages:")
        for page in result["pages"][:2]:
            print(f"page_number = {page['page_number']}")
            print(page["text"][:300])
            print()

    if result.get("evidence"):
        print("First evidence:")
        for item in result["evidence"][:3]:
            print(item)

    if result.get("error"):
        print(f"\nerror = {result['error']}")


if __name__ == "__main__":
    main()