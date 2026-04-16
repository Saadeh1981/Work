from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.services.catalog_mapper import map_to_catalog
from backend.services.extraction_orchestrator import run_extraction_plan
from backend.services.output_builder import build_output_v1


CATALOG_PATH = Path("backend/config/field_catalog.json")


def load_catalog() -> dict[str, Any]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    print("DEBUG loaded catalog site fields:", [f["key"] for f in catalog.get("site_fields", [])])
    return catalog

def build_pipeline_output(summary, env: str, run_id: str, created_utc: str):
    extraction_results = run_extraction_plan(summary)
    catalog = load_catalog()

    mapped_items = []
    for item in extraction_results:
        mapped = map_to_catalog(item, catalog)
        mapped_items.append(mapped)

    return build_output_v1(
        parsed_items=mapped_items,
        env=env,
        run_id=run_id,
        created_utc=created_utc,
    )