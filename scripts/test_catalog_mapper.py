from __future__ import annotations

import json
from pathlib import Path

from backend.services.catalog_mapper import map_to_catalog


def main() -> None:
    catalog_path = Path("data/field_catalog.json")

    if not catalog_path.exists():
        print(f"Catalog file not found: {catalog_path}")
        return

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    sample_item = {
        "filename": "SUSD - Fillmore.pdf",
        "extracted": {
            "PlantName": "SUSD-FILLMORE ES",
            "ac_capacity_mw": 0.10248,
            "dc_capacity_mw": 0.10248,
            "module_count": 336,
            "module_models": ["CS6X-305"],
            "inverter_models": ["SMA STP 24000TL-US"],
            "inverter_count": 4,
        },
        "_raw_text": """
            PROJECT NAME: SUSD-FILLMORE ES
            AC CAPACITY: 102.48 kW
            DC CAPACITY: 102.48 kW
            TOTAL MODULES: 336
            MODULE MODEL: CS6X-305
        """,
        "_extraction_meta": {
            "PlantName": {
                "confidence": 0.91,
                "evidence": "PROJECT NAME: SUSD-FILLMORE ES",
                "source": "pdf_page_text",
            },
            "ac_capacity_mw": {
                "confidence": 0.88,
                "evidence": "AC CAPACITY: 102.48 kW",
                "source": "derived",
            },
            "dc_capacity_mw": {
                "confidence": 0.88,
                "evidence": "DC CAPACITY: 102.48 kW",
                "source": "derived",
            },
            "module_count": {
                "confidence": 0.86,
                "evidence": "TOTAL MODULES: 336",
                "source": "derived_text",
            },
            "module_models": {
                "confidence": 0.84,
                "evidence": "MODULE MODEL: CS6X-305",
                "source": "derived_text",
            },
            "inverter_models": {
                "confidence": 0.82,
                "evidence": "SMA STP 24000TL-US",
                "source": "library_or_base",
            },
        },
        "warnings": {
            "low_confidence_fields": []
        },
    }

    payload = map_to_catalog(sample_item, catalog)

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()