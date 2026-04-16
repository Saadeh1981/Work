from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from backend.services.excel.excel_model_exporter import ExcelModelExporter


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export engineering model workbook from output_v1.json"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to output_v1.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output .xlsx",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    data = load_json(input_path)

    exporter = ExcelModelExporter()
    saved_path = exporter.export(data, output_path)

    print(f"Excel workbook written to: {saved_path}")


if __name__ == "__main__":
    main()