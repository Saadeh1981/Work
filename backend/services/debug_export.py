import csv
from pathlib import Path

def export_plants_to_csv(output_v1, filepath: str):
    path = Path(filepath)

    rows = []

    for plant in output_v1.overview.plants:
        row = {
            "plant_id": plant.plant_id,
            "plant_name": plant.plant_name,
            "plant_type": plant.plant_type,
            "dc_kw": plant.capacity.get("dc_kw"),
            "ac_kw": plant.capacity.get("ac_kw"),
        }

        for meta in plant.metadata:
            row[f"meta_{meta.field}"] = meta.value

        rows.append(row)

    if not rows:
        return

    fieldnames = sorted({k for r in rows for k in r.keys()})

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
