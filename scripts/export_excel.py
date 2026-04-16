from pathlib import Path
import json

from backend.services.excel.excel_model_exporter import ExcelModelExporter


def get_latest_run_folder(base_path: Path) -> Path:
    runs = [p for p in base_path.iterdir() if p.is_dir()]
    if not runs:
        raise Exception("No run folders found")
    return sorted(runs)[-1]


def count_review_rows(output: dict) -> int:
    count = 0

    def walk(node):
        nonlocal count

        for a in node.get("attributes", []):
            for ev in a.get("evidence", []):
                if isinstance(ev, dict) and ev.get("needs_review"):
                    count += 1
                    break

        for child in node.get("children", []):
            if isinstance(child, dict):
                walk(child)

    for plant in output.get("devices", {}).get("plants", []):
        for node in plant.get("device_tree", []):
            if isinstance(node, dict):
                walk(node)

    return count


def main() -> None:
    runs_base = Path("data/runs")
    latest_run = get_latest_run_folder(runs_base)

    input_path = latest_run / "output_v1.json"
    output_path = latest_run / "output_model.xlsx"

    print(f"Using run folder: {latest_run}")
    print(f"Input: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        output = json.load(f)

    print(f"Rows needing review: {count_review_rows(output)}")

    exporter = ExcelModelExporter()
    final_path = exporter.export(output=output, output_path=output_path)

    print(f"Excel exported to: {final_path}")


if __name__ == "__main__":
    main()