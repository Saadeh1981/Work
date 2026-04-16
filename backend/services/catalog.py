from pathlib import Path
import json

def load_field_catalog() -> dict:
    base = Path(__file__).resolve().parents[1]  # backend/
    catalog_path = base / "config" / "field_catalog.json"

    if not catalog_path.exists():
        raise FileNotFoundError(f"Missing field_catalog.json at {catalog_path}")

    return json.loads(catalog_path.read_text(encoding="utf-8"))
