from __future__ import annotations

from typing import Any


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {}


def _get_files(summary: Any) -> list[dict[str, Any]]:
    summary_dict = _to_dict(summary)
    files = summary_dict.get("files") or []
    return [f for f in files if isinstance(f, dict)]


def _get_sections(file_entry: dict[str, Any]) -> list[str]:
    sections = file_entry.get("sections") or []
    labels = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        label = sec.get("label")
        if label:
            labels.append(_norm(label))
    return labels


def classify_file(file_entry: dict[str, Any]) -> dict[str, Any]:
    name = _norm(file_entry.get("file_name"))
    sections = _get_sections(file_entry)

    tags: set[str] = set()
    relevance = "maybe"

    if "pv" in name or "solar" in name:
        tags.add("solar")
    if "bess" in name or "battery" in name:
        tags.add("bess")
    if "substation" in name:
        tags.add("substation")
    if "fire alarm" in name or " fa " in f" {name} " or "_fa_" in name:
        tags.add("fire_alarm")
    if "datasheet" in name or "data sheet" in name:
        tags.add("vendor_datasheet")
    if (
        "sql" in name
        or "indcomms" in name
        or "gps" in name
        or "gmm" in name
        or "grs" in name
    ):
        tags.add("vendor_datasheet")
    if "wiring" in name:
        tags.add("wiring")
    if "physical as-built" in name or "physical as-builts" in name:
        tags.add("physical")
    if "record drawing" in name or "record_drawing" in name:
        tags.add("record_drawing")
    if "construction set" in name:
        tags.add("construction_set")

    if any("plant_metadata" in s for s in sections):
        tags.add("plant_metadata")
    if any("single_line_diagram" in s for s in sections):
        tags.add("single_line")
    if any("equipment_schedule" in s for s in sections):
        tags.add("equipment_schedule")
    if any("layout" in s for s in sections):
        tags.add("layout")

    exclude_tags = {"vendor_datasheet", "fire_alarm", "substation", "wiring", "physical"}
    strong_keep_tags = {"solar", "record_drawing", "construction_set", "plant_metadata", "single_line"}

    if tags & exclude_tags:
        relevance = "exclude"
    elif tags & strong_keep_tags:
        relevance = "keep"

    return {
        "file_name": file_entry.get("file_name"),
        "tags": sorted(tags),
        "relevance": relevance,
    }


def triage_summary_files(summary: Any) -> list[dict[str, Any]]:
    files = _get_files(summary)
    return [classify_file(f) for f in files]


def build_demo_file_subset(
    summary: Any,
    triage: list[dict[str, Any]],
    mode: str = "solar_demo",
) -> Any:
    allowed_names = set()

    for item in triage:
        tags = set(item.get("tags") or [])
        relevance = item.get("relevance")

        if mode == "solar_demo":
            if relevance == "keep" and "solar" in tags:
                allowed_names.add(item["file_name"])
            elif relevance == "keep" and "construction_set" in tags and "bess" not in tags:
                allowed_names.add(item["file_name"])
            elif relevance == "keep" and "record_drawing" in tags and "bess" not in tags:
                allowed_names.add(item["file_name"])

    # keep original object type if possible
    if hasattr(summary, "model_copy"):
        filtered_files = [
            f for f in summary.files
            if getattr(f, "file_name", None) in allowed_names
        ]
        return summary.model_copy(update={"files": filtered_files})

    # fallback for dict-like summaries
    summary_dict = _to_dict(summary)
    filtered_files = []
    for f in summary_dict.get("files") or []:
        if isinstance(f, dict) and f.get("file_name") in allowed_names:
            filtered_files.append(f)

    new_summary = dict(summary_dict)
    new_summary["files"] = filtered_files
    new_summary["_triage"] = triage
    return new_summary