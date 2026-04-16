from __future__ import annotations

import sys
from pathlib import Path

from backend.services.docx_target_extractor import extract_docx_content


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_docx_target_extractor <docx_path>")
        return

    path = Path(sys.argv[1])
    result = extract_docx_content(path)

    print(f"status = {result['status']}")
    print(f"paragraph_count = {result['paragraph_count']}")
    print(f"table_count = {result['table_count']}")
    print(f"row_count = {result['row_count']}")

    if result["paragraphs"]:
        print("\nFirst paragraphs:")
        for item in result["paragraphs"][:5]:
            print(f"- {item}")

    if result.get("paragraph_evidence"):
        print("\nFirst paragraph evidence:")
        for item in result["paragraph_evidence"][:3]:
            print(item)

    if result["tables"]:
        print("\nFirst table rows:")
        for row in result["tables"][0][:5]:
            print(row)

    if result.get("table_evidence"):
        print("\nFirst table evidence:")
        for item in result["table_evidence"][:3]:
            print(item)

    if result["error"]:
        print(f"\nerror = {result['error']}")


if __name__ == "__main__":
    main()