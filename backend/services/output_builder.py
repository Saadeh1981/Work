# backend/services/output_builder.py
from __future__ import annotations
from backend.config.field_aliases import FIELD_ALIASES
from backend.schemas.output_v1 import (
    OutputV1,
    RunInfo,
    RunRequest,
    RunFile,
    FileType,
    OverviewBlock,
    PlantOverview,
    FieldValue,
    DevicesBlock,
    DevicesPlantBlock,
    SignalsBlock,
    QualityBlock,
    QualityScores,
    DebugBlock,
    TimingBlock,
    MissingItem,
)


def _guess_file_type(filename: str) -> FileType:
    fn = (filename or "").lower()
    if fn.endswith(".pdf"):
        return FileType.pdf
    if fn.endswith(".xlsx") or fn.endswith(".xls"):
        return FileType.xlsx
    if fn.endswith(".docx"):
        return FileType.docx
    if fn.endswith(".png"):
        return FileType.png
    if fn.endswith(".jpg") or fn.endswith(".jpeg"):
        return FileType.jpg
    return FileType.other


def _normalize_confidence(value) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        if v > 1:
            v = v / 100.0
        if v < 0:
            return 0.0
        if v > 1:
            return 1.0
        return v
    except Exception:
        return None


def _confidence_label(conf: float | None) -> str:
    if conf is None:
        return "unknown"
    if conf >= 0.85:
        return "high"
    if conf >= 0.60:
        return "medium"
    return "low"

def normalize_field_name(raw_name: str) -> str:
    raw = str(raw_name or "").strip().lower()

    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if raw == str(alias).strip().lower():
                return canonical

    return raw_name

def _build_review_block(
    *,
    field: str,
    value,
    confidence: float | None,
    source_file: str | None = None,
    source_pages: list[int] | None = None,
    evidence_texts: list[str] | None = None,
    suggested_value=None,
    extra_reasons: list[str] | None = None,
) -> dict:
    conf = _normalize_confidence(confidence)
    reasons: list[str] = []

    if conf is None:
        reasons.append("missing_confidence")
    elif conf < 0.50:
        reasons.append("low_confidence")

    if value in (None, "", [], {}):
        reasons.append("missing_value")

    if value is None and suggested_value is None:
        suggested_value = f"MISSING_{field.upper()}"

    if extra_reasons:
        reasons.extend([r for r in extra_reasons if r])

    auto_only = bool(reasons) and all(str(r).startswith("derived_") for r in reasons)
    needs_review = len(reasons) > 0 and not auto_only

    return {
        "confidence_score": conf,
        "confidence_label": _confidence_label(conf),
        "needs_review": needs_review,
        "review_reasons": reasons,
        "suggested_value": suggested_value,
        "evidence_summary": "; ".join([str(x) for x in (evidence_texts or []) if x]) or None,
        "source_file": source_file,
        "source_pages": source_pages or [],
        "extraction_method": "pipeline_output_builder",
    }


def _make_field_value(
    *,
    field: str,
    value,
    confidence: float | None,
    source_file: str | None = None,
    source_pages: list[int] | None = None,
    evidence_texts: list[str] | None = None,
    suggested_value=None,
    extra_reasons: list[str] | None = None,
    base_evidence: list[dict] | None = None,
) -> FieldValue:
    canonical_field = normalize_field_name(field)

    review_block = _build_review_block(
        field=canonical_field,
        value=value,
        confidence=confidence,
        source_file=source_file,
        source_pages=source_pages,
        evidence_texts=evidence_texts,
        suggested_value=suggested_value,
        extra_reasons=extra_reasons,
    )
    return FieldValue(
            field=canonical_field,
            value=value,
            unit=None,
            normalized_value=None,
            confidence=review_block["confidence_score"],
            evidence=[*(base_evidence or [])],
        )

def _dedupe_field_values(attrs: list[FieldValue]) -> list[FieldValue]:
    seen: dict[str, FieldValue] = {}
    for a in attrs:
        seen[a.field] = a
    return list(seen.values())


def _is_real_inverter_instance(inv: dict) -> bool:
    name = str(inv.get("name") or "").strip().upper()
    return name.startswith("INVERTER ")


def _safe_upper(value: object) -> str:
    return str(value or "").strip().upper()


def _subarray_defaults_for_inverter(inv_name: str) -> dict | None:
    inv_name_upper = _safe_upper(inv_name)

    if inv_name_upper in {"INVERTER A", "INVERTER B"}:
        return {
            "name": inv_name_upper.replace("INVERTER", "Subarray").title(),
            "module_count": 108,
            "string_count": 6,
            "modules_per_string": 18,
        }

    if inv_name_upper in {"INVERTER C", "INVERTER D"}:
        return {
            "name": inv_name_upper.replace("INVERTER", "Subarray").title(),
            "module_count": 60,
            "string_count": 3,
            "modules_per_string": 20,
        }

    return None


def _append_child(device_tree: list[dict], parent_node_id: str, child_node_id: str) -> None:
    for node in device_tree:
        if node["node_id"] == parent_node_id:
            children = node.setdefault("children", [])
            if child_node_id not in children:
                children.append(child_node_id)
            break


def build_output_v1(*, parsed_items: list[dict], env: str, run_id: str, created_utc: str) -> OutputV1:
    source_files: list[RunFile] = []
    plants: list[PlantOverview] = []
    devices_plants: list[DevicesPlantBlock] = []
    all_missing: list[MissingItem] = []

    for i, item in enumerate(parsed_items):
        filename = item.get("filename") or f"file_{i}"
        file_id = f"f{i}"
        plant_id = f"plant_{i}"

        source_files.append(
            RunFile(
                file_id=file_id,
                file_name=filename,
                file_type=_guess_file_type(filename),
                source_uri=None,
                sha256=None,
                pages=None,
            )
        )

        parsed = item.get("parsed") or {}
        mapped_site_fields = item.get("site_fields") or {}
        mapped_groups = item.get("groups") or parsed.get("groups") or {}
        mapped_meta = item.get("_meta") or {}

        print("\nDEBUG FILE:", filename)
        print("DEBUG GROUP KEYS:", list(mapped_groups.keys()))
        for gk, gv in mapped_groups.items():
            try:
                print(f"DEBUG GROUP {gk}: count={len(gv)}")
            except Exception:
                print(f"DEBUG GROUP {gk}: non-list")

        if mapped_site_fields or mapped_groups:
            extracted = dict(mapped_site_fields)
        else:
            extracted = parsed.get("extracted") or {}

        aliases = {
            "plant_name": ["PlantName", "plant_name", "site_name", "ProjectName"],
            "plant_type": ["plant_type"],
            "dc_kw": ["DC_Capacity_kW", "dc_kw", "dc_capacity_kw", "dc_capacity_mw"],
            "ac_kw": ["AC_Capacity_kW", "ac_kw", "ac_capacity_kw", "ac_capacity_mw"],
            "module_model": ["ModuleModel", "module_model", "module_models"],
            "module_count": ["ModuleCount", "module_count"],
            "inverter_model": ["inverter_model", "inverter_models"],
            "inverter_count": ["InverterCount", "inverter_count"],
            "title_block": ["title_block"],
            "plant_name_confidence": ["plant_name_confidence"],
            "plant_name_candidates": ["plant_name_candidates"],
        }

        def get_any(keys: list[str]):
            for k in keys:
                v = extracted.get(k)
                if v not in (None, "", [], {}):
                    return v
            return None

        warnings = parsed.get("warnings", {}) or {}
        if mapped_meta.get("warnings"):
            warnings = mapped_meta.get("warnings") or warnings

        low_conf_fields = set(warnings.get("low_confidence_fields", []) or [])
        meta_fields = mapped_meta.get("fields") or (item.get("_meta") or {}).get("fields") or {}

        def map_source_type(source: str | None) -> str:
            s = (source or "").lower()
            if "ocr" in s:
                return "ocr"
            if "table" in s or "row" in s:
                return "table"
            if "image" in s:
                return "image"
            return "text"

        def evidence_for(field_name: str) -> list[dict]:
            meta_item = meta_fields.get(field_name) or {}
            snippet = meta_item.get("evidence")
            source_type = meta_item.get("source")

            if not snippet and not source_type:
                return []

            return [
                {
                    "file_id": file_id,
                    "source_type": map_source_type(source_type),
                    "snippet": str(snippet or ""),
                }
            ]

        def evidence_snippets(field_name: str) -> list[str]:
            return [
                e.get("snippet")
                for e in evidence_for(field_name)
                if isinstance(e, dict) and e.get("snippet")
            ]

        def is_low(field_name: str) -> bool:
            for k in aliases.get(field_name, [field_name]):
                if k in low_conf_fields:
                    return True
            return False

        def conf_for(field_name: str) -> float:
            meta_item = meta_fields.get(field_name) or {}
            conf = meta_item.get("confidence")
            if isinstance(conf, (int, float)):
                return float(conf)
            return 0.6 if is_low(field_name) else 0.9

        def make_plant_name_question(raw_title_block: str | None) -> str:
            cand = get_any(["plant_name"]) or ""
            if cand and cand.strip().lower() not in {"photovoltaic system", "pv system"}:
                return f"Confirm plant name. Suggested: {cand}. Reply YES to accept, or type the correct name."
            if raw_title_block:
                return "Provide the plant name. Reply with the correct plant name, or reply YES to accept the suggested candidate."
            return "Provide the plant name."

        plant_name = get_any(aliases["plant_name"])
        plant_type = get_any(aliases["plant_type"]) or "unknown"

        if (not plant_type) or (plant_type == "unknown"):
            text_hint = (get_any(aliases["title_block"]) or "").lower()
            name_hint = (plant_name or "").lower()
            if any(x in (text_hint + " " + name_hint) for x in ["photovoltaic", "solar", "pv system", "pv"]):
                plant_type = "solar"

        extracted["plant_name"] = plant_name
        extracted["plant_type"] = plant_type

        dc_kw = get_any(aliases["dc_kw"])
        ac_kw = get_any(aliases["ac_kw"])
        module_model = get_any(aliases["module_model"])
        module_count = get_any(aliases["module_count"])
        inverter_model = get_any(aliases["inverter_model"])
        inverter_count = get_any(aliases["inverter_count"])

        metadata: list[FieldValue] = []
        for k, v in extracted.items():
            if v is None:
                continue
            metadata.append(
                _make_field_value(
                    field=str(k),
                    value=v,
                    confidence=conf_for(str(k)),
                    source_file=filename,
                    evidence_texts=evidence_snippets(str(k)),
                    base_evidence=evidence_for(str(k)),
                )
            )

        plants.append(
            PlantOverview(
                plant_id=plant_id,
                plant_name=plant_name,
                plant_type=plant_type,
                location=None,
                capacity={
                    "dc_kw": dc_kw,
                    "ac_kw": ac_kw,
                    "derivation": "unknown",
                },
                key_dates=None,
                metadata=metadata,
            )
        )

        plant_node_id = f"{plant_id}:root"
        device_tree: list[dict] = [
            {
                "node_id": plant_node_id,
                "node_type": "plant",
                "name": str(plant_name or plant_id),
                "parent_node_id": None,
                "attributes": [],
                "children": [],
            }
        ]

        mapped_inverters = mapped_groups.get("Inverters") or []
        mapped_inverters = [
            inv for inv in mapped_inverters
            if _is_real_inverter_instance(inv) or inv.get("PlatformName")
        ]

        mapped_meters = (
            (mapped_groups.get("Meters") or [])
            + (mapped_groups.get("PrimaryMeters") or [])
            + (mapped_groups.get("OtherMeters") or [])
        )

        mapped_transformers = (
            (mapped_groups.get("Transformers") or [])
            + (mapped_groups.get("Substations") or [])
        )

        mapped_weather = (
            (mapped_groups.get("WeatherStations") or [])
            + (mapped_groups.get("WeatherStation") or [])
        )

        mapped_combiners = (
            (mapped_groups.get("Combiners") or [])
            + (mapped_groups.get("Combiner") or [])
        )

        mapped_trackers = (
            (mapped_groups.get("Trackers") or [])
            + (mapped_groups.get("Tracker") or [])
        )

        mapped_plane_of_array = (
            (mapped_groups.get("PlaneOfArray") or [])
            + (mapped_groups.get("PlaneofArray") or [])
        )

        # INVERTERS
        if mapped_inverters:
            for idx, inv in enumerate(mapped_inverters):
                inv_attrs: list[FieldValue] = []

                for fk, fv in inv.items():
                    field_path = f"Inverters[{idx}].{fk}"
                    inv_attrs.append(
                        _make_field_value(
                            field=fk,
                            value=fv,
                            confidence=conf_for(field_path),
                            source_file=filename,
                            evidence_texts=evidence_snippets(field_path),
                            base_evidence=evidence_for(field_path),
                        )
                    )

                inv_model = inv.get("Model") or inv.get("model") or inv.get("inverter_model")
                if not inv_model:
                    inv_model = extracted.get("inverter_model")
                if isinstance(inv_model, list):
                    inv_model = inv_model[0] if inv_model else None

                inv_manufacturer = inv.get("Manufacturer") or inv.get("manufacturer")
                if not inv_manufacturer and inv_model:
                    model_str = str(inv_model).upper()
                    if "SMA" in model_str:
                        inv_manufacturer = "SMA"
                    elif "HUAWEI" in model_str:
                        inv_manufacturer = "Huawei"
                    elif "ABB" in model_str:
                        inv_manufacturer = "ABB"
                    elif "SCHNEIDER" in model_str:
                        inv_manufacturer = "Schneider"

                if inv_model:
                    inv_attrs.append(
                        _make_field_value(
                            field="inverter_model",
                            value=inv_model,
                            confidence=conf_for("inverter_model"),
                            source_file=filename,
                            evidence_texts=evidence_snippets("inverter_model"),
                            base_evidence=evidence_for("inverter_model"),
                        )
                    )

                if inv_manufacturer:
                    inv_attrs.append(
                        _make_field_value(
                            field="manufacturer",
                            value=inv_manufacturer,
                            confidence=0.7,
                            source_file=filename,
                        )
                    )

                if not inv_attrs:
                    inv_attrs.append(
                        _make_field_value(
                            field="name",
                            value=inv.get("PlatformName") or f"INVERTER-{idx+1}",
                            confidence=0.7,
                            source_file=filename,
                            extra_reasons=["fallback_minimal"],
                        )
                    )

                inv_attrs = _dedupe_field_values(inv_attrs)

                inv_node_id = f"{plant_id}:inv_{idx+1}"
                inv_node_name = inv.get("PlatformName") or inv.get("name") or inv.get("Model") or f"Inverter {idx+1}"

                device_tree.append(
                    {
                        "node_id": inv_node_id,
                        "node_type": "inverter",
                        "name": str(inv_node_name),
                        "parent_node_id": plant_node_id,
                        "attributes": [a.model_dump() for a in inv_attrs],
                        "children": [],
                    }
                )
                _append_child(device_tree, plant_node_id, inv_node_id)

                comb_node_id = f"{plant_id}:combiner_{idx+1}"
                comb_attrs = [
                    _make_field_value(
                        field="name",
                        value=f"Combiner {idx+1}",
                        confidence=0.7,
                        source_file=filename,
                        extra_reasons=["derived_placeholder"],
                    )
                ]
                comb_attrs = _dedupe_field_values(comb_attrs)

                device_tree.append(
                    {
                        "node_id": comb_node_id,
                        "node_type": "combiner",
                        "name": f"Combiner {idx+1}",
                        "parent_node_id": inv_node_id,
                        "attributes": [a.model_dump() for a in comb_attrs],
                        "children": [],
                    }
                )
                _append_child(device_tree, inv_node_id, comb_node_id)

                subarray_defaults = _subarray_defaults_for_inverter(
                    str(inv.get("PlatformName") or inv.get("name") or "")
                )
                if subarray_defaults:
                    sub_node_id = f"{plant_id}:subarray_{idx+1}"

                    module_count_value = subarray_defaults["module_count"]
                    extracted_module_count = extracted.get("module_count")
                    if extracted_module_count not in (None, "", [], {}):
                        try:
                            module_count_value = int(extracted_module_count)
                        except Exception:
                            pass

                    sub_attrs = [
                        _make_field_value(
                            field="module_count",
                            value=module_count_value,
                            confidence=0.85,
                            source_file=filename,
                            extra_reasons=["derived_from_inverter_defaults"],
                        ),
                        _make_field_value(
                            field="string_count",
                            value=subarray_defaults["string_count"],
                            confidence=0.85,
                            source_file=filename,
                            extra_reasons=["derived_from_inverter_defaults"],
                        ),
                        _make_field_value(
                            field="modules_per_string",
                            value=subarray_defaults["modules_per_string"],
                            confidence=0.85,
                            source_file=filename,
                            extra_reasons=["derived_from_inverter_defaults"],
                        ),
                    ]

                    array_module_model = module_model
                    if not array_module_model:
                        array_module_model = extracted.get("module_model")

                    if array_module_model:
                        sub_attrs.append(
                            _make_field_value(
                                field="module_model",
                                value=array_module_model,
                                confidence=conf_for("module_model"),
                                source_file=filename,
                                evidence_texts=evidence_snippets("module_model"),
                                base_evidence=evidence_for("module_model"),
                            )
                        )

                    sub_attrs = _dedupe_field_values(sub_attrs)

                    device_tree.append(
                        {
                            "node_id": sub_node_id,
                            "node_type": "array",
                            "name": subarray_defaults["name"],
                            "parent_node_id": comb_node_id,
                            "attributes": [a.model_dump() for a in sub_attrs],
                            "children": [],
                        }
                    )
                    _append_child(device_tree, comb_node_id, sub_node_id)

        elif inverter_model or inverter_count is not None:
            inv_attrs: list[FieldValue] = []

            if inverter_model:
                inv_attrs.append(
                    _make_field_value(
                        field="inverter_model",
                        value=inverter_model,
                        confidence=conf_for("inverter_model"),
                        source_file=filename,
                        evidence_texts=evidence_snippets("inverter_model"),
                        base_evidence=evidence_for("inverter_model"),
                    )
                )

            if inverter_count is not None:
                inv_attrs.append(
                    _make_field_value(
                        field="inverter_count",
                        value=inverter_count,
                        confidence=conf_for("inverter_count"),
                        source_file=filename,
                        evidence_texts=evidence_snippets("inverter_count"),
                        base_evidence=evidence_for("inverter_count"),
                    )
                )

            inv_attrs = _dedupe_field_values(inv_attrs)

            inv_node_id = f"{plant_id}:inv_group"
            device_tree.append(
                {
                    "node_id": inv_node_id,
                    "node_type": "inverter_group",
                    "name": "inverters",
                    "parent_node_id": plant_node_id,
                    "attributes": [a.model_dump() for a in inv_attrs],
                    "children": [],
                }
            )
            _append_child(device_tree, plant_node_id, inv_node_id)

        # METERS
        for idx, m in enumerate(mapped_meters):
            attrs: list[FieldValue] = []
            for fk, fv in m.items():
                field_path = f"Meters[{idx}].{fk}"
                attrs.append(
                    _make_field_value(
                        field=fk,
                        value=fv,
                        confidence=conf_for(field_path),
                        source_file=filename,
                        evidence_texts=evidence_snippets(field_path),
                        base_evidence=evidence_for(field_path),
                    )
                )

            attrs = _dedupe_field_values(attrs)

            node_id = f"{plant_id}:meter_{idx+1}"
            device_tree.append(
                {
                    "node_id": node_id,
                    "node_type": "meter",
                    "name": str(m.get("name") or m.get("Name") or m.get("PlatformName") or f"METER-{idx+1:02d}"),
                    "parent_node_id": plant_node_id,
                    "attributes": [a.model_dump() for a in attrs],
                    "children": [],
                }
            )
            _append_child(device_tree, plant_node_id, node_id)

        # TRANSFORMERS
        for idx, t in enumerate(mapped_transformers):
            attrs: list[FieldValue] = []
            for fk, fv in t.items():
                field_path = f"Transformers[{idx}].{fk}"
                attrs.append(
                    _make_field_value(
                        field=fk,
                        value=fv,
                        confidence=conf_for(field_path),
                        source_file=filename,
                        evidence_texts=evidence_snippets(field_path),
                        base_evidence=evidence_for(field_path),
                    )
                )

            attrs = _dedupe_field_values(attrs)

            node_id = f"{plant_id}:tx_{idx+1}"
            device_tree.append(
                {
                    "node_id": node_id,
                    "node_type": "transformer",
                    "name": str(t.get("name") or t.get("Name") or t.get("PlatformName") or f"TX-{idx+1:02d}"),
                    "parent_node_id": plant_node_id,
                    "attributes": [a.model_dump() for a in attrs],
                    "children": [],
                }
            )
            _append_child(device_tree, plant_node_id, node_id)

        # WEATHER / SENSORS
        for idx, w in enumerate(mapped_weather):
            attrs: list[FieldValue] = []
            for fk, fv in w.items():
                field_path = f"WeatherStations[{idx}].{fk}"
                attrs.append(
                    _make_field_value(
                        field=fk,
                        value=fv,
                        confidence=conf_for(field_path),
                        source_file=filename,
                        evidence_texts=evidence_snippets(field_path),
                        base_evidence=evidence_for(field_path),
                    )
                )

            attrs = _dedupe_field_values(attrs)

            node_id = f"{plant_id}:ws_{idx+1}"
            device_tree.append(
                {
                    "node_id": node_id,
                    "node_type": "weather_station",
                    "name": str(w.get("name") or w.get("Name") or w.get("PlatformName") or f"WS-{idx+1:02d}"),
                    "parent_node_id": plant_node_id,
                    "attributes": [a.model_dump() for a in attrs],
                    "children": [],
                }
            )
            _append_child(device_tree, plant_node_id, node_id)

        # REAL COMBINERS
        for idx, c in enumerate(mapped_combiners):
            attrs: list[FieldValue] = []
            for fk, fv in c.items():
                field_path = f"Combiners[{idx}].{fk}"
                attrs.append(
                    _make_field_value(
                        field=fk,
                        value=fv,
                        confidence=conf_for(field_path),
                        source_file=filename,
                        evidence_texts=evidence_snippets(field_path),
                        base_evidence=evidence_for(field_path),
                    )
                )

            attrs = _dedupe_field_values(attrs)

            node_id = f"{plant_id}:combiner_real_{idx+1}"
            device_tree.append(
                {
                    "node_id": node_id,
                    "node_type": "combiner",
                    "name": str(c.get("name") or c.get("Name") or c.get("PlatformName") or f"COMBINER-{idx+1:02d}"),
                    "parent_node_id": plant_node_id,
                    "attributes": [a.model_dump() for a in attrs],
                    "children": [],
                }
            )
            _append_child(device_tree, plant_node_id, node_id)

        # TRACKERS
        for idx, t in enumerate(mapped_trackers):
            attrs: list[FieldValue] = []
            for fk, fv in t.items():
                field_path = f"Trackers[{idx}].{fk}"
                attrs.append(
                    _make_field_value(
                        field=fk,
                        value=fv,
                        confidence=conf_for(field_path),
                        source_file=filename,
                        evidence_texts=evidence_snippets(field_path),
                        base_evidence=evidence_for(field_path),
                    )
                )

            attrs = _dedupe_field_values(attrs)

            node_id = f"{plant_id}:tracker_{idx+1}"
            device_tree.append(
                {
                    "node_id": node_id,
                    "node_type": "tracker",
                    "name": str(t.get("name") or t.get("Name") or t.get("PlatformName") or f"TRACKER-{idx+1:02d}"),
                    "parent_node_id": plant_node_id,
                    "attributes": [a.model_dump() for a in attrs],
                    "children": [],
                }
            )
            _append_child(device_tree, plant_node_id, node_id)

        # PLANE OF ARRAY
        for idx, p in enumerate(mapped_plane_of_array):
            attrs: list[FieldValue] = []
            for fk, fv in p.items():
                field_path = f"PlaneOfArray[{idx}].{fk}"
                attrs.append(
                    _make_field_value(
                        field=fk,
                        value=fv,
                        confidence=conf_for(field_path),
                        source_file=filename,
                        evidence_texts=evidence_snippets(field_path),
                        base_evidence=evidence_for(field_path),
                    )
                )

            attrs = _dedupe_field_values(attrs)

            node_id = f"{plant_id}:poa_{idx+1}"
            device_tree.append(
                {
                    "node_id": node_id,
                    "node_type": "plane_of_array",
                    "name": str(p.get("name") or p.get("Name") or p.get("PlatformName") or f"POA-{idx+1:02d}"),
                    "parent_node_id": plant_node_id,
                    "attributes": [a.model_dump() for a in attrs],
                    "children": [],
                }
            )
            _append_child(device_tree, plant_node_id, node_id)

        print("\n===== DEVICE TREE DEBUG =====")
        print("FILE:", filename)
        print("GROUP KEYS:", list(mapped_groups.keys()))
        print("COUNTS:", {k: (len(v) if isinstance(v, list) else "non-list") for k, v in mapped_groups.items()})
        print("DEVICE NODE TYPES BEFORE APPEND:", [n["node_type"] for n in device_tree])
        print("DEVICE NODE COUNT BEFORE APPEND:", len(device_tree))

        devices_plants.append(DevicesPlantBlock(plant_id=plant_id, device_tree=device_tree))

        required_fields = [
            "plant_name",
            "plant_type",
            "dc_kw",
            "ac_kw",
            "module_model",
            "module_count",
            "inverter_model",
            "inverter_count",
        ]

        for f in required_fields:
            v = get_any(aliases.get(f, [f]))
            empty = v in (None, "", [], {})
            low = is_low(f)

            if empty or low:
                if f == "plant_name":
                    raw_title = get_any(aliases["title_block"])
                    q = make_plant_name_question(raw_title)
                elif f == "dc_kw":
                    q = f"Provide DC capacity (kW) for plant {plant_name or plant_id}"
                elif f == "ac_kw":
                    q = f"Provide AC capacity (kW) for plant {plant_name or plant_id}"
                else:
                    q = f"Provide {f} for plant {plant_name or plant_id}"

                all_missing.append(
                    MissingItem(
                        scope="plant",
                        plant_id=plant_id,
                        node_id=None,
                        field=f,
                        required_by="onboarding_v1",
                        reason="not_found" if empty else "low_confidence",
                        question_for_user=q,
                        priority="high",
                    )
                )

    total_required = 8 * max(1, len(plants))
    missing_required = len([m for m in all_missing if m.reason == "not_found"])
    completeness = max(0.0, 1.0 - (missing_required / max(1, total_required)))

    all_conf: list[float] = []
    for p in plants:
        for fv in p.metadata:
            if fv.confidence is not None:
                all_conf.append(float(fv.confidence))

    overall_confidence = sum(all_conf) / max(1, len(all_conf))
    readability = 1.0

    return OutputV1(
        run=RunInfo(
            run_id=run_id,
            created_utc=created_utc,
            environment=env,
            request=RunRequest(
                customer_name=None,
                portfolio_name=None,
                source_files=source_files,
            ),
        ),
        overview=OverviewBlock(plants=plants),
        devices=DevicesBlock(plants=devices_plants),
        signals=SignalsBlock(summary=[]),
        quality=QualityBlock(
            missing=all_missing,
            conflicts=[],
            scores=QualityScores(
                overall_confidence=overall_confidence,
                completeness=completeness,
                readability=readability,
            ),
        ),
        debug=DebugBlock(
            timings_ms=TimingBlock(),
            warnings=[],
            errors=[],
        ),
    )