from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re
import shutil
import zipfile

from backend.services.output_builder import build_output_v1
from backend.services.pipeline_runner import load_catalog
from backend.services.catalog_mapper import map_to_catalog

from backend.services.summary_engine import summarize_folder
from backend.services.extraction_orchestrator import run_extraction_plan

from backend.services.builders.onboarding_record_builder import build_onboarding_record
from backend.services.validators.required_fields_validator import validate_required_fields
from backend.services.validators.confidence_validator import validate_confidence_and_review
from backend.services.resolvers.timezone_resolver import resolve_timezone
from backend.services.resolvers.ac_capacity_resolver import resolve_ac_capacity

INPUT_DIR = Path("inputs")
OUTPUT_DIR = Path("data/runs")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

def expand_input_archives(input_dir: Path, working_input_dir: Path) -> None:
    ensure_dir(working_input_dir)

    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() == ".zip":
            extract_dir = working_input_dir / path.stem
            ensure_dir(extract_dir)

            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(extract_dir)

            print(f"ZIP extracted: {path.name} -> {extract_dir}")
        else:
            destination = working_input_dir / path.name
            shutil.copy2(path, destination)


def prepare_runtime_input_dir(source_input_dir: Path, run_dir: Path) -> Path:
    runtime_input_dir = run_dir / "expanded_inputs"
    expand_input_archives(source_input_dir, runtime_input_dir)

    total_files = [p for p in runtime_input_dir.rglob("*") if p.is_file()]
    print(f"TOTAL INPUT FILES AFTER EXPAND: {len(total_files)}")

    return runtime_input_dir

def run_light_phase(input_dir: Path):
    """
    Phase 1:
    - scan all files
    - preflight
    - summary
    - extraction plan
    """
    summary = summarize_folder(str(input_dir))
    return summary


def run_deep_phase(summary):
    """
    Phase 2:
    - extraction
    - catalog mapping
    - final OutputV1
    """
    from backend.services.file_triage import triage_summary_files, build_demo_file_subset

    triage = triage_summary_files(summary)

    filtered_summary = build_demo_file_subset(
        summary,
        triage,
        mode="solar_demo"
    )

    print("DEBUG triage kept files:")
    for f in filtered_summary.files:
        print("-", f.file_name)

    extraction_results = run_extraction_plan(filtered_summary)
    catalog = load_catalog()

    mapped_items = []
    for item in extraction_results:
        adapted_item = adapt_extraction_item_for_catalog(item)
        mapped = map_to_catalog(adapted_item, catalog)
        mapped = enrich_mapped_item_from_text(mapped, adapted_item)
        mapped.setdefault("_meta", {})["raw_text"] = adapted_item.get("_raw_text") or ""
        mapped_items.append(mapped)

    mapped_items = aggregate_mapped_items(mapped_items)

    created_utc = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")

    output = None
    try:
        output = build_output_v1(
            parsed_items=mapped_items,
            env="dev",
            run_id=run_id,
            created_utc=created_utc,
        )
    except Exception as e:
        print("\nWARNING: build_output_v1 failed")
        print(str(e))

    return extraction_results, mapped_items, output


def adapt_extraction_item_for_catalog(item: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes orchestrator output into the shape expected by catalog_mapper.
    """
    file_name = item.get("file_name") or item.get("filename") or "unknown_file"

    extracted_block = item.get("extracted") or {}

    raw_text = ""
    extraction_meta: dict[str, Any] = {}

    file_type = item.get("file_type")

    if file_type == "pdf":
        raw_text = (
            extracted_block.get("combined_text")
            or extracted_block.get("text")
            or extracted_block.get("_raw_text")
            or ""
        )
        extraction_meta["pdf_has_text"] = bool(raw_text.strip())
        evidence = extracted_block.get("evidence") or []
        for ev in evidence:
            page = ev.get("page")
            extraction_meta_key = f"page_{page}" if page is not None else "pdf_text"
            extraction_meta[extraction_meta_key] = {
                "confidence": ev.get("confidence"),
                "evidence": ev.get("snippet"),
                "source": ev.get("method"),
            }

    elif file_type == "docx":
        paragraphs = extracted_block.get("paragraphs") or []
        raw_text = "\n".join(paragraphs)

        for idx, ev in enumerate(extracted_block.get("paragraph_evidence") or []):
            extraction_meta[f"paragraph_{idx}"] = {
                "confidence": ev.get("confidence"),
                "evidence": ev.get("snippet"),
                "source": ev.get("method"),
            }

    elif file_type == "xlsx":
        rows = extracted_block.get("rows") or []
        raw_text = "\n".join(str(r) for r in rows)

        for idx, ev in enumerate(extracted_block.get("row_evidence") or []):
            extraction_meta[f"row_{idx}"] = {
                "confidence": ev.get("confidence"),
                "evidence": ev.get("snippet"),
                "source": ev.get("method"),
            }

    return {
        "filename": file_name,
        "file_type": file_type,
        "extracted": extracted_block,
        "_raw_text": raw_text,
        "_extraction_meta": extraction_meta,
        "warnings": {},
    }


def _set_if_empty(d: dict[str, Any], key: str, value: Any) -> None:
    if value in (None, "", [], {}):
        return
    if d.get(key) in (None, "", [], {}):
        d[key] = value


def _ensure_group_list(groups: dict[str, Any], group_name: str) -> list[dict[str, Any]]:
    value = groups.get(group_name)
    if not isinstance(value, list):
        value = []
        groups[group_name] = value
    return value


def _dedupe_by_keys(items: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        sig = tuple(str(item.get(k, "")).strip().upper() for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def _clean_text_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip(" :,-")
    return value or None


def _extract_first(
    text: str,
    patterns: list[str],
    flags: int = re.IGNORECASE | re.DOTALL,
) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            if match.lastindex:
                return _clean_text_value(match.group(1))
            return _clean_text_value(match.group(0))
    return None


def _extract_module_make_model(text: str) -> tuple[str | None, str | None]:
    patterns = [
        r"\b(CANADIAN\s+SOLAR|TRINA|JINKO|JA\s+SOLAR|REC|QCELLS|FIRST\s+SOLAR)\s+([A-Z0-9\-]{5,})",
        r"\bMODULE(?:S)?[:\s]+([A-Z][A-Z0-9 &\-/]+?)\s+([A-Z0-9\-]{5,})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            make = _clean_text_value(match.group(1))
            model = _clean_text_value(match.group(2))

            # reject bad matches
            bad_words = {"ENGINEER", "RECORD", "DRAWING", "TITLE"}
            if make and make.upper() in bad_words:
                continue
            if model and model.upper() in bad_words:
                continue

            return make, model

    return None, None

import re
from typing import Any

def _extract_inverter_entries(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    patterns = [
        r"\((\d+)\)\s+([A-Z0-9 &\-/]+?)\s+((?:[A-Z]{1,5}[0-9][A-Z0-9\-_/.]*))\s+1500V\s+INVERTERS?",
        r"INVERTER\s+([A-Z0-9]+)\s*[:\-]?\s+UTILITY INTERACTIVE INVERTER\s+([A-Z0-9][A-Z0-9 &\-/]+?)\s+((?:[A-Z]{1,4}[0-9][A-Z0-9\-_/.]*))\b",
        r"INVERTER\s+\d+\s+SPECS.*?MAKE\s+([A-Z0-9][A-Z0-9 &\-/]+?)\s+MODEL\s+((?:[A-Z]{1,4}[0-9][A-Z0-9\-_/.]*))\s+QUANTITY\s+(\d+)",
        r"INVERTER\s*[:\-]?\s*MAKE\s+([A-Z0-9][A-Z0-9 &\-/]+?)\s+MODEL\s+((?:[A-Z]{1,4}[0-9][A-Z0-9\-_/.]*))",
        r"INVERTER(?:\s+\d+)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9 &\-/]+?)\s+((?:[A-Z]{1,5}[0-9][A-Z0-9\-_/.]*))(?:\s+QTY\s*[:\-]?\s*(\d+))?",
        r"([A-Z0-9][A-Z0-9 &\-/]+?)\s+((?:SUNEYE|SUNPOWER|SMA|POWER-ONE|ABB|FRONIUS|SOLAREDGE|SCHNEIDER|SATCON)[A-Z0-9 &\-/.]*)\s+((?:[A-Z]{1,5}[0-9][A-Z0-9\-_/.]*))(?:\s+QTY\s*[:\-]?\s*(\d+))?",
        r"Inverter\s+\d+\s+Qty\.\s*(\d+),\s*([A-Z0-9 &\-]+)\s+([A-Z0-9_\-\.]+)"
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            groups = [g.strip() if isinstance(g, str) else g for g in match.groups()]

            quantity = 1
            manufacturer = None
            model = None

            digit_groups = [g for g in groups if g is not None and str(g).isdigit()]
            text_groups = [g for g in groups if g is not None and not str(g).isdigit()]

            if digit_groups:
                quantity = int(digit_groups[0])

            if len(text_groups) >= 2:
                manufacturer = _clean_text_value(text_groups[0])
                model = _clean_text_value(text_groups[1])
            elif len(groups) == 2:
                manufacturer = _clean_text_value(groups[0])
                model = _clean_text_value(groups[1])

            if not model:
                continue

            for _ in range(quantity):
                entries.append(
                    {
                        "name": f"Inverter {len(entries) + 1}",
                        "manufacturer": manufacturer,
                        "model": model,
                        "quantity": 1,
                    }
                )

    return entries


def _extract_city_state_from_address(address: str) -> str | None:
    if not address:
        return None

    patterns = [
        r"\b([A-Z][A-Z\s]+,\s*[A-Z]{2})\b",
        r"\b([A-Z][A-Z\s]+,\s*[A-Z]{2,})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, address.upper())
        if match:
            return _clean_text_value(match.group(1))
    return None


def _extract_generic_city_state(text: str) -> str | None:
    matches = re.findall(r"\b([A-Z][A-Z\s]+,\s*[A-Z]{2,})\b", text.upper())

    blacklist = {
        "DRAWING",
        "TITLE",
        "SCALE",
    }

    for match in matches:
        value = _clean_text_value(match)
        if not value:
            continue
        if value in blacklist:
            continue
        return value

    return None


def enrich_mapped_item_from_text(mapped: dict[str, Any], adapted_item: dict[str, Any]) -> dict[str, Any]:
    text = adapted_item.get("_raw_text") or ""
    if not text:
        return mapped

    text_upper = text.upper()

    site_fields = mapped.setdefault("site_fields", {})
    groups = mapped.setdefault("groups", {})

    dc_patterns = [
        r"(\d[\d,]*)\s*W\s*DC[- ]?STC",
        r"(\d[\d,]*)\s*KW\s*DC",
        r"DC\s*CAPACITY\s*[:\-]?\s*(\d[\d,]*)\s*KW",
        r"PROJECT\s*CAPACITY\s*[:\-]?\s*(\d[\d,]*)\s*KW\s*DC",
    ]

    for pattern in dc_patterns:
        m = re.search(pattern, text_upper)
        if m:
            value = float(m.group(1).replace(",", ""))
            if value > 1000:
                dc_kw = round(value / 1000.0, 3)
            else:
                dc_kw = round(value, 3)

            _set_if_empty(site_fields, "DC_Capacity_kW", dc_kw)
            break

    # fallback: derive DC from modules
    if site_fields.get("DC_Capacity_kW") in (None, "", [], {}):
        module_count = site_fields.get("ModuleCount")
        module_model = site_fields.get("ModuleModel")

        inferred_watt = None

        if isinstance(module_model, str):
            match = re.search(r"(\d{3,4})", module_model)
            if match:
                inferred_watt = float(match.group(1))

        try:
            module_count = float(module_count) if module_count not in (None, "", [], {}) else None
        except (TypeError, ValueError):
            module_count = None

        if module_count and inferred_watt:
            dc_kw = round((module_count * inferred_watt) / 1000.0, 3)
            _set_if_empty(site_fields, "DC_Capacity_kW", dc_kw)
    qty_match = re.search(r"\bMODULE(?:S)?\s*(?:QTY\.?|COUNT)?[:\s]*([0-9]{2,5})\b", text_upper)
    if not qty_match:
        qty_match = re.search(r"\b([0-9]{2,5})\s+[A-Z][A-Z0-9 &\-/]+?\s+[A-Z]{1,4}[0-9][A-Z0-9\-_/.]*\b", text_upper)

    if qty_match:
        qty = int(qty_match.group(1))
        if qty >= 10:
            _set_if_empty(site_fields, "ModuleCount", qty)

    module_make, module_model = _extract_module_make_model(text_upper)
    if module_make:
        _set_if_empty(site_fields, "ModuleMake", module_make)
    if module_model:
        _set_if_empty(site_fields, "ModuleModel", module_model)

    address_value = site_fields.get("Address")
    location_value = None

    if isinstance(address_value, str):
        location_value = _extract_city_state_from_address(address_value)

    if not location_value:
        location_value = _extract_generic_city_state(text)

    if location_value:
        _set_if_empty(site_fields, "site_location", location_value)

    inverter_group = _ensure_group_list(groups, "Inverters")
    for inv in _extract_inverter_entries(text_upper):
        inverter_group.append(inv)
    groups["Inverters"] = _dedupe_by_keys(groups["Inverters"], ["name"])

    meter_group = _ensure_group_list(groups, "Meters")

    for match in re.finditer(r"UTILITY METER\s*#\s*([0-9]+)", text_upper):
        meter_group.append(
            {
                "name": f"Utility Meter {match.group(1)}",
                "meter_number": match.group(1),
                "meter_type": "UTILITY",
            }
        )

    for match in re.finditer(r"\bMETER\s*#\s*([0-9]+)", text_upper):
        meter_group.append(
            {
                "name": f"Meter {match.group(1)}",
                "meter_number": match.group(1),
            }
        )

    if "208/120 WYE" in text_upper:
        for item in meter_group:
            _set_if_empty(item, "voltage", "208/120 WYE")

    groups["Meters"] = _dedupe_by_keys(groups["Meters"], ["meter_number"])

    transformer_group = _ensure_group_list(groups, "Transformers")

    tx_matches = re.finditer(r"TRANSFORMER\s+([0-9A-Z/]+)\s+(\d+KVA)", text_upper)
    for i, match in enumerate(tx_matches, start=1):
        voltage, kva = match.groups()
        transformer_group.append(
            {
                "name": f"Transformer {i}",
                "voltage": voltage.strip(),
                "power_rating": kva.strip(),
            }
        )

    if "TRANSFORMER" in text_upper and "480Y/208Y" in text_upper:
        transformer_group.append(
            {
                "name": "Transformer 1",
                "voltage": "480Y/208Y",
                "power_rating": "75kVA" if "75KVA" in text_upper else None,
            }
        )

    groups["Transformers"] = _dedupe_by_keys(groups["Transformers"], ["name", "voltage", "power_rating"])

    weather_group = _ensure_group_list(groups, "WeatherStations")

    if "AMBIENT TEMPERATURE SENSOR" in text_upper:
        weather_group.append({"name": "Ambient Temp Sensor", "sensor_type": "Temperature"})

    if "CELL TEMPERATURE SENSOR" in text_upper:
        weather_group.append({"name": "Cell Temp Sensor", "sensor_type": "Temperature"})

    if "PYRANOMETER" in text_upper:
        weather_group.append({"name": "Pyranometer", "sensor_type": "Irradiance"})

    if "ALSO ENERGY" in text_upper:
        weather_group.append({"name": "Also Energy Monitor", "sensor_type": "Monitoring"})

    groups["WeatherStations"] = _dedupe_by_keys(groups["WeatherStations"], ["name"])

    return mapped


def _best_value(values: list[Any]) -> Any:
    cleaned = [v for v in values if v not in (None, "", [], {})]
    if not cleaned:
        return None

    for v in cleaned:
        if isinstance(v, str) and v.strip().upper() not in {"DRAWING", "TITLE", "SCALE"}:
            return v

    return cleaned[0]


def _merge_group_items(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    combined = list(existing) + list(incoming)
    seen = set()
    out = []

    for item in combined:
        sig = tuple(str(item.get(k, "")).strip().upper() for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)

    return out


def aggregate_mapped_items(mapped_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Merge page-level mapped items into one record per source file.
    """
    by_filename: dict[str, dict[str, Any]] = {}

    for item in mapped_items:
        meta = item.get("_meta", {}) if isinstance(item.get("_meta"), dict) else {}
        filename = meta.get("filename") or "unknown_file"

        if filename not in by_filename:
            by_filename[filename] = {
                "version": item.get("version", "1.0"),
                "site_fields": {},
                "groups": {},
                "_meta": {
                    "fields": {},
                    "warnings": {},
                    "filename": filename,
                    "raw_text": "",
                },
            }
        filename_upper = filename.upper()

        noise_file_tokens = [
            "MANUAL",
            "INSTRUCTIONS",
            "REGISTER MAP",
            "MODBUS",
            "USER MANUAL",
        ]

        is_reference_doc = any(token in filename_upper for token in noise_file_tokens)
        agg = by_filename[filename]

        site_fields = item.get("site_fields", {}) if isinstance(item.get("site_fields"), dict) else {}
        for key, value in site_fields.items():
            current = agg["site_fields"].get(key)
            agg["site_fields"][key] = _best_value([current, value])

        src_fields = meta.get("fields", {}) if isinstance(meta.get("fields"), dict) else {}
        agg["_meta"]["fields"].update(src_fields)

        src_warnings = meta.get("warnings", {}) if isinstance(meta.get("warnings"), dict) else {}
        agg["_meta"]["warnings"].update(src_warnings)

        src_raw_text = meta.get("raw_text")
        if isinstance(src_raw_text, str) and src_raw_text.strip():
            existing_raw_text = agg["_meta"].get("raw_text", "")
            if src_raw_text not in existing_raw_text:
                agg["_meta"]["raw_text"] = f"{existing_raw_text}\n{src_raw_text}".strip()
        groups = item.get("groups", {}) if isinstance(item.get("groups"), dict) else {}
        for group_name, group_items in groups.items():
            if not isinstance(group_items, list):
                continue

            if group_name not in agg["groups"]:
                agg["groups"][group_name] = []

            dedupe_keys = {
                "Inverters": ["name"],
                "Meters": ["meter_number", "name"],
                "Transformers": ["name", "voltage", "power_rating"],
                "WeatherStations": ["name"],
            }.get(group_name, ["name"])

            agg["groups"][group_name] = _merge_group_items(
                agg["groups"][group_name],
                group_items,
                dedupe_keys,
            )

    return list(by_filename.values())


def infer_plant_type(mapped_items: list[dict[str, Any]]) -> str:
    text_blob = json.dumps(mapped_items).upper()

    if "INVERTER" in text_blob or "MODULE" in text_blob or "PYRANOMETER" in text_blob:
        return "solar"
    if "TURBINE" in text_blob:
        return "wind"
    if "BATTERY" in text_blob or "PCS" in text_blob:
        return "bess"
    if "HYDRO" in text_blob:
        return "hydro"

    return "unknown"


def infer_project_name(mapped_items: list[dict[str, Any]]) -> str | None:
    for item in mapped_items:
        site_fields = item.get("site_fields", {})
        if site_fields.get("project_name"):
            return str(site_fields["project_name"])
        if site_fields.get("PlantName"):
            return str(site_fields["PlantName"])
        if site_fields.get("plant_name"):
            return str(site_fields["plant_name"])
        if site_fields.get("site_name"):
            return str(site_fields["site_name"])
    return None


def build_raw_fields_from_mapped_items(mapped_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_fields: list[dict[str, Any]] = []
    BAD_MODULE_VALUES = {
        "DATA",
        "SHEET",
        "LIQUID",
        "COOLING",
        "MODULE",
    }

    BAD_LOCATION_PATTERNS = [
        "PASEO PADRE",
        "ALAMEDA",
        "BLYMYER",
        "ENGINEERS",
        "COVER SHEET",
        "ELECTRICAL",
    ]
    field_name_map = {
        "PlantName": "project_name",
        "site_name": "site_name",
        "site_location": "site_location",
        "DC_Capacity_kW": "dc_capacity_kw",
        "ModuleMake": "module_manufacturer",
        "ModuleModel": "module_model",
        "Address": "address",
        "Country": "country",
        "Latitude": "lat",
        "Longitude": "long",
    }
    seen = set()

    def add_field(
        name: str,
        raw_value: Any,
        normalized_value: Any,
        filename: str,
        section: str,
        snippet: str,
        confidence: float = 0.9,
        status: str = "valid",
    ) -> None:
        if normalized_value in (None, "", [], {}):
            return
        # ---- FILTER MODULE FIELDS
        if name in {"module_manufacturer", "module_model"}:
            if isinstance(normalized_value, str):
                val = normalized_value.strip().upper()
                if val in BAD_MODULE_VALUES:
                    return

        # ---- FILTER SITE LOCATION / ADDRESS NOISE
        if name in {"site_location", "address"}:
            if isinstance(normalized_value, str):
                val = normalized_value.upper()

                if any(p in val for p in BAD_LOCATION_PATTERNS):
                    return

                if "MWAC" in val:
                    return

                if len(normalized_value.strip()) < 10:
                    return

                if "," not in normalized_value:
                    return

        if name in {"project_name", "site_name"} and isinstance(normalized_value, str):
            cleaned_name = normalized_value.strip().upper()
            if cleaned_name in {
                "ES",
                "DRAWING",
                "TITLE",
                "SCALE",
                "TITLE SHEET",
                "AS BUILT",
                "FOR CONSTRUCTION",
                "SYMBOL",
                "BATTERY",
                "BESS FIELD",
                "BLOCK ARRAY CONFIGURATION",
                "LINETYPE LEGEND",
                "WARNING SIGNS",
                "KEYED NOTES",
                "CIVIL DETAILS",
                "AREA 1 & 2 SITE MAP",
                "INVERTER 1.1.1",
                "INVERTER SPECIFIC WARNING",
                "COMBINER HARNESS NAMING CONVENTION",
                "COMBINER HARNESS AT TRACKER",
                "DC FEEDER TRENCH",
                "EQUIPMENT SPECIFICATIONS",
                "FIBER OPTIC DIAGRAM",
                "ZONE A",
                "BLYMYER",
                "DANGER",
                "50' UTILITY",
            }:
                return

        sig = (name, str(normalized_value).strip().upper())
        if sig in seen:
            return

        seen.add(sig)
        raw_fields.append(
            {
                "name": name,
                "raw_value": raw_value,
                "normalized_value": normalized_value,
                "confidence": confidence,
                "evidence": [
                    {
                        "file_name": filename,
                        "page": None,
                        "sheet": None,
                        "section": section,
                        "snippet": snippet,
                    }
                ],
                "status": status,
            }
        )

    for item in mapped_items:
        site_fields = item.get("site_fields", {}) if isinstance(item.get("site_fields"), dict) else {}
        groups = item.get("groups", {}) if isinstance(item.get("groups"), dict) else {}
        meta = item.get("_meta", {}) if isinstance(item.get("_meta"), dict) else {}
        filename = meta.get("filename", "unknown_file")

    for source_key, value in site_fields.items():
        is_reference_doc = False
        if is_reference_doc and source_key in {
            "PlantName",
            "site_name",
            "site_location",
            "Address",
            "ModuleMake",
            "ModuleModel",
            "Country",
            "Latitude",
            "Longitude",
        }:
            continue

            normalized_value = value
            if source_key == "DC_Capacity_kW":
                try:
                    normalized_value = float(value)
                except (TypeError, ValueError):
                    normalized_value = value

            add_field(
                name=target_name,
                raw_value=value,
                normalized_value=normalized_value,
                filename=filename,
                section="site_fields",
                snippet=f"{source_key}: {value}",
            )

            if target_name == "project_name":
                add_field(
                    name="site_name",
                    raw_value=value,
                    normalized_value=normalized_value,
                    filename=filename,
                    section="site_fields",
                    snippet=f"{source_key}: {value}",
                    confidence=0.85,
                )

        timezone_result = resolve_timezone(
            raw_text=item.get("_meta", {}).get("raw_text", ""),
            address=site_fields.get("Address"),
            site_location=site_fields.get("site_location"),
            explicit_timezone=site_fields.get("SiteTimeZone"),
        
            
        )

        if timezone_result.value:
            add_field(
                name="timezone",
                raw_value=timezone_result.value,
                normalized_value=timezone_result.value,
                filename=filename,
                section="site_fields",
                snippet=timezone_result.evidence or f"Resolved timezone from {timezone_result.source}",
                confidence=timezone_result.confidence,
            )
        groups = item.get("groups", {}) if isinstance(item.get("groups"), dict) else {}
        raw_text_for_ac = item.get("_meta", {}).get("raw_text", "") or ""
        text_upper = raw_text_for_ac.upper()
        inverter_idx = text_upper.find("INVERTER")
        print("DEBUG ac inverter_idx:", inverter_idx)

        if inverter_idx != -1:
            start = max(0, inverter_idx - 400)
            end = min(len(raw_text_for_ac), inverter_idx + 2000)
            print("DEBUG ac inverter_window:")
            print(raw_text_for_ac[start:end])

        direct_inverter_hits = _extract_inverter_entries(text_upper)
        group_inverters = groups.get("Inverters", []) if isinstance(groups, dict) else []

        print("DEBUG ac filename:", filename)
        print("DEBUG ac raw_text_len:", len(raw_text_for_ac))
        print("DEBUG ac groups_keys:", list(groups.keys()) if isinstance(groups, dict) else None)
        print("DEBUG ac group_inverters_count:", len(group_inverters))
        print("DEBUG ac group_inverters_preview:", group_inverters[:5])
        print("DEBUG ac direct_inverter_hits_count:", len(direct_inverter_hits))
        print("DEBUG ac direct_inverter_hits_preview:", direct_inverter_hits[:5])
        print(
            "DEBUG ac text_flags:",
            {
                "has_kw_ac": "KW-AC" in text_upper,
                "has_ac_capacity": "AC CAPACITY" in text_upper,
                "has_project_capacity": "PROJECT CAPACITY" in text_upper,
                "has_inverter": "INVERTER" in text_upper,
                "has_kw": "KW" in text_upper,
                "has_mw": "MW" in text_upper,
            },
        )
        print("DEBUG ac raw_text_sample:", filename, raw_text_for_ac[:1000])

        ac_result = resolve_ac_capacity(
            raw_text=raw_text_for_ac,
            site_fields=site_fields,
            groups=groups,
        )
        print("DEBUG ac_result:", filename, ac_result)

        if ac_result.value_kw is not None:
            add_field(
                name="ac_capacity_kw",
                raw_value=ac_result.value_kw,
                normalized_value=ac_result.value_kw,
                filename=filename,
                section="site_fields",
                snippet=ac_result.evidence or f"Resolved AC capacity from {ac_result.source}",
                confidence=ac_result.confidence,
            )
       
        # ---- DC CAPACITY FALLBACK (for demo)
        if site_fields.get("DC_Capacity_kW") in (None, "", [], {}):
            ac_val = site_fields.get("AC_Capacity_kW")

            try:
                if ac_val:
                    dc_estimated = round(float(ac_val) * 1.3, 3)

                    add_field(
                        name="dc_capacity_kw",
                        raw_value=dc_estimated,
                        normalized_value=dc_estimated,
                        filename=filename,
                        section="derived",
                        snippet="Estimated DC capacity from AC * 1.3",
                        confidence=0.6,
                        status="low_confidence",
                    )
            except (TypeError, ValueError):
                pass
        meter_group = groups.get("Meters", [])
        transformer_group = groups.get("Transformers", [])

        for meter in meter_group:
            voltage = meter.get("voltage")
            if isinstance(voltage, str):
                match = re.search(r"(\d+(?:\.\d+)?)", voltage)
                if match:
                    add_field(
                        name="interconnection_voltage_kv",
                        raw_value=voltage,
                        normalized_value=float(match.group(1)),
                        filename=filename,
                        section="Meters",
                        snippet=f"Meter voltage: {voltage}",
                        confidence=0.8,
                    )

        for transformer in transformer_group:
            voltage = transformer.get("voltage")
            if isinstance(voltage, str):
                match = re.search(r"(\d+(?:\.\d+)?)", voltage)
                if match:
                    add_field(
                        name="interconnection_voltage_kv",
                        raw_value=voltage,
                        normalized_value=float(match.group(1)),
                        filename=filename,
                        section="Transformers",
                        snippet=f"Transformer voltage: {voltage}",
                        confidence=0.75,
                    )

    return raw_fields


def print_onboarding_summary(record) -> None:
    print("\nONBOARDING SUMMARY")
    print(f"Project Name: {record.project_name}")
    print(f"Plant Type: {record.plant_type}")
    print(f"Readiness Status: {record.readiness_status}")

    print("\nEXTRACTED FIELDS")
    if not record.fields:
        print("- None")
    else:
        for field in record.fields:
            print(
                f"- {field.name}: {field.normalized_value} "
                f"(confidence={field.confidence}, status={field.status})"
            )

    print("\nVALIDATION ISSUES")
    if not record.validation_issues:
        print("- None")
    else:
        for issue in record.validation_issues:
            print(
                f"- {issue.field_name}: {issue.issue_type} "
                f"[{issue.severity}] {issue.message}"
            )


def main() -> None:
    if not INPUT_DIR.exists():
        print(f"Input folder not found: {INPUT_DIR}")
        return

    created_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUTPUT_DIR / created_utc
    ensure_dir(run_dir)

    runtime_input_dir = prepare_runtime_input_dir(INPUT_DIR, run_dir)

    print("Running light phase...")
    summary = run_light_phase(runtime_input_dir)

    if hasattr(summary, "model_dump"):
        summary_json = summary.model_dump()
    elif hasattr(summary, "dict"):
        summary_json = summary.dict()
    else:
        summary_json = summary

    save_json(run_dir / "summary.json", summary_json)
    print(f"Saved: {run_dir / 'summary.json'}")

    print("Running deep phase...")
    extraction_results, mapped_items, output = run_deep_phase(summary)

    save_json(run_dir / "extraction_results.json", extraction_results)
    print(f"Saved: {run_dir / 'extraction_results.json'}")

    save_json(run_dir / "mapped_items.json", mapped_items)
    print(f"Saved: {run_dir / 'mapped_items.json'}")

    if output is not None:
        if hasattr(output, "model_dump"):
            output_json = output.model_dump()
        elif hasattr(output, "dict"):
            output_json = output.dict()
        else:
            output_json = output

        save_json(run_dir / "output_v1.json", output_json)
        print(f"Saved: {run_dir / 'output_v1.json'}")
    else:
        print("Skipped saving output_v1.json because build_output_v1 failed.")

    source_files = [
        item.get("_meta", {}).get("filename", "unknown_file")
        for item in mapped_items
    ]
    source_files = list(dict.fromkeys(source_files))

    plant_type = infer_plant_type(mapped_items)
    project_name = infer_project_name(mapped_items)
    raw_fields = build_raw_fields_from_mapped_items(mapped_items)

    if project_name:
        raw_fields.append(
            {
                "name": "project_name",
                "raw_value": project_name,
                "normalized_value": project_name,
                "confidence": 0.95,
                "evidence": [
                    {
                        "file_name": source_files[0] if source_files else "unknown_file",
                        "page": None,
                        "sheet": None,
                        "section": "derived",
                        "snippet": f"Derived project name: {project_name}",
                    }
                ],
                "status": "valid",
            }
        )

    raw_fields.append(
        {
            "name": "plant_type",
            "raw_value": plant_type,
            "normalized_value": plant_type,
            "confidence": 0.95,
            "evidence": [
                {
                    "file_name": source_files[0] if source_files else "unknown_file",
                    "page": None,
                    "sheet": None,
                    "section": "derived",
                    "snippet": f"Derived plant type: {plant_type}",
                }
            ],
            "status": "valid",
        }
    )
    raw_fields.append(
        {
            "name": "energy_type",
            "raw_value": plant_type,
            "normalized_value": plant_type,
            "confidence": 0.95,
            "evidence": [
                {
                    "file_name": source_files[0] if source_files else "unknown_file",
                    "page": None,
                    "sheet": None,
                    "section": "derived",
                    "snippet": f"Derived energy type: {plant_type}",
                }
            ],
            "status": "valid",
        }
    )

    deduped_raw_fields = []
    seen = set()
    for field in raw_fields:
        sig = (field["name"], str(field["normalized_value"]).strip().upper())
        if sig in seen:
            continue
        seen.add(sig)
        deduped_raw_fields.append(field)

    record = build_onboarding_record(
        project_name=project_name,
        plant_type=plant_type,
        source_files=source_files,
        raw_fields=deduped_raw_fields,
        site_fields=mapped_items[0].get("site_fields") or {} if mapped_items else {},
    )

    record = validate_required_fields(record)
    print("\nAFTER REQUIRED FIELDS VALIDATION")
    for issue in record.validation_issues:
        print(f"- {issue.field_name}: {issue.issue_type}")
    print(f"Status after required fields: {record.readiness_status}")

    record = validate_confidence_and_review(record)

    save_json(run_dir / "onboarding_record.json", record.model_dump())
    print(f"Saved: {run_dir / 'onboarding_record.json'}")

    print_onboarding_summary(record)

    print("\nPipeline completed.")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()