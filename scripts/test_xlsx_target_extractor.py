from __future__ import annotations

import sys
from pathlib import Path

from backend.services.xlsx_target_extractor import extract_xlsx_sheet


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.test_xlsx_target_extractor <xlsx_path> <sheet_name>")
        return

    path = Path(sys.argv[1])
    sheet_name = sys.argv[2]

    result = extract_xlsx_sheet(str(path), sheet_name)

    print(f"status = {result['status']}")
    print(f"sheet_name = {result['sheet_name']}")
    print(f"row_count = {result['row_count']}")

    if result["headers"]:
        print("\nHeaders:")
        print(result["headers"])

    if result["rows"]:
        print("\nFirst rows:")
        for row in result["rows"][:3]:
            print(row)

    if result.get("row_evidence"):
        print("\nFirst row evidence:")
        for item in result["row_evidence"][:3]:
            print(item)

    if result.get("error"):
        print(f"\nerror = {result['error']}")


if __name__ == "__main__":
    main()