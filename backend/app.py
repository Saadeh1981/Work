from __future__ import annotations

import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.api.native_extract import router as native_extract_router
from backend.schemas.output_v1 import OutputV1
from backend.schemas.summary import SummaryRequest, SummaryResponse
from backend.security.auth import require_api_key_except_public
from backend.services import learning
from backend.services.apply_library import apply_library, flag_low_confidence
from backend.services.catalog import load_field_catalog
from backend.services.catalog_mapper import map_to_catalog
from backend.services.debug_export import export_plants_to_csv
from backend.services.docint_client import DocumentIntelligenceClient
from backend.services.extractors import parse_asbuilt
from backend.services.native_parser_router import build_preflight_summary, parse_native
from backend.services.output_builder import build_output_v1
from backend.services.pdf_utils import rasterize_pdf_to_jpegs, slice_first_pages
from backend.services.rules_engine import extract_from_yaml, find_rules_file, load_rules_file
from backend.services.suggest import suggest_mappings
from backend.services.summary_engine import summarize_folder


load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent  # .../backend
CATALOG_PATH = BASE_DIR / "config" / "field_catalog.json"
catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

APP_NAME = os.getenv("APP_NAME", "ai-onboarding")
APP_ENV = os.getenv("APP_ENV", "local")
APP_VERSION = os.getenv("APP_VERSION", "0.0.1")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(APP_NAME)

app = FastAPI(
    title="AI Onboarding (MVP Skeleton)",
    version=APP_VERSION,
    dependencies=[Depends(require_api_key_except_public)],
)

app.include_router(native_extract_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _mask(v: str | None, keep: int = 4) -> str | None:
    if not v:
        return None
    v = str(v)
    return "*" * max(0, len(v) - keep) + v[-keep:]


MAX_INLINE_BYTES = 15 * 1024 * 1024  # ~15 MB guard


def _is_size_error(err: dict) -> bool:
    return isinstance(err, dict) and err.get("error") and (
        err.get("error_kind") == "size_limit"
        or "InvalidContentLength" in str(err.get("code") or "")
        or "too large" in str(err.get("message") or "").lower()
        or "too large" in str(err.get("text") or "").lower()
    )


async def _analyze_with_retry(raw: bytes, content_type: str, start_pages: int = 8):
    di = DocumentIntelligenceClient()

    if content_type != "application/pdf":
        return await di.analyze_read(raw, content_type=content_type)

    pages = max(1, start_pages)
    pdf_bytes = raw

    if len(pdf_bytes) > MAX_INLINE_BYTES:
        pdf_bytes = slice_first_pages(pdf_bytes, max_pages=pages)

    while True:
        res = await di.analyze_read(pdf_bytes, content_type="application/pdf")

        if isinstance(res, dict) and res.get("error"):
            if _is_size_error(res) and pages > 1:
                pages = max(1, pages // 2)
                pdf_bytes = slice_first_pages(raw, max_pages=pages)
                continue

            if _is_size_error(res):
                imgs = rasterize_pdf_to_jpegs(raw, max_pages=min(start_pages, 4), dpi=120)
                if not imgs:
                    return {"error": True, "stage": "rasterize", "text": "No images produced from PDF"}

                combined = []
                for img in imgs:
                    r = await di.analyze_read(img, content_type="image/jpeg")
                    if isinstance(r, dict) and r.get("error"):
                        return r
                    ar = (r or {}).get("analyzeResult", {}) or {}
                    combined.append(ar.get("content") or "")

                return {
                    "status": "succeeded",
                    "analyzeResult": {"content": "\n\n".join([c for c in combined if c])},
                }

            return res

        return res


async def _run_read_ocr(file: UploadFile, first_pages: int = 8):
    ct = file.content_type or "application/pdf"
    if ct not in ("application/pdf", "image/png", "image/jpeg"):
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {ct}")

    raw = await file.read()
    result = await _analyze_with_retry(raw, ct, start_pages=first_pages)

    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=502, detail=result)

    return result


def _flatten_read_text(result: dict) -> str:
    ar = (result or {}).get("analyzeResult") or {}
    flat = ar.get("content")
    if flat:
        return flat

    lines = []
    for p in ar.get("pages", []) or []:
        for ln in p.get("lines", []) or []:
            t = ln.get("content")
            if t:
                lines.append(t)

    return "\n".join(lines)


class Healthz(BaseModel):
    status: str
    name: str
    env: str
    version: str


@app.get("/healthz", response_model=Healthz, tags=["ops"])
def healthz():
    return Healthz(status="ok", name=APP_NAME, env=APP_ENV, version=APP_VERSION)


@app.get("/version", tags=["ops"])
def version():
    return {"version": APP_VERSION}


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.get("/env", tags=["ops"])
def env_view():
    return {
        "DOCINT_ENDPOINT": os.getenv("DOCINT_ENDPOINT"),
        "DOCINT_KEY": _mask(os.getenv("DOCINT_KEY")),
        "DOCINT_PREFER": os.getenv("DOCINT_PREFER", "auto"),
        "RULES_PATH": os.getenv("RULES_PATH"),
    }


@app.get("/ops/env-check", tags=["ops"])
def env_check():
    return {
        "have_endpoint": bool(os.getenv("DOCINT_ENDPOINT")),
        "have_key": bool(os.getenv("DOCINT_KEY")),
        "have_public_api_key": bool(os.getenv("PUBLIC_API_KEY")),
        "have_public_api_key_next": bool(os.getenv("PUBLIC_API_KEY_NEXT")),
    }


class LearnRequest(BaseModel):
    name: str
    pattern: str
    target_column: str | None = None


@app.get("/metadata/library", tags=["metadata"])
async def get_metadata_library():
    return {"fields": learning.list_fields()}


@app.get("/metadata/catalog", tags=["metadata"])
def metadata_catalog():
    return load_field_catalog()


@app.post("/metadata/learn", tags=["metadata"])
async def learn_metadata(req: LearnRequest):
    rec = learning.upsert_field(req.name, req.pattern, req.target_column)
    return rec


class SuggestRequest(BaseModel):
    unknown_metadata: list[dict]


@app.post("/extract/native-test", tags=["extract"])
async def native_test(
    file: UploadFile = File(...),
    max_pages: int = Query(25, ge=1, le=200),
    include_blocks: bool = Query(False),
):
    raw = await file.read()
    return parse_native(
        filename=file.filename or "file",
        file_bytes=raw,
        max_pages=max_pages,
        include_blocks=include_blocks,
    )


@app.post("/metadata/suggest", tags=["metadata"])
def metadata_suggest(req: SuggestRequest):
    return suggest_mappings(req.unknown_metadata)


@app.post("/extract/read-test", tags=["extract"])
async def read_test(file: UploadFile = File(...), first_pages: int = 8):
    result = await _run_read_ocr(file, first_pages=first_pages)

    ar = (result or {}).get("analyzeResult", {}) or {}
    page_count = len(ar.get("pages", []) or [])
    sample_lines = []
    for p in (ar.get("pages") or [])[:2]:
        for ln in (p.get("lines") or [])[:5]:
            t = ln.get("content")
            if t:
                sample_lines.append(t)

    return {"status": "succeeded", "pageCount": page_count, "sampleLines": sample_lines}


@app.post("/extract/asbuilt/batch", tags=["extract"], response_model=OutputV1)
async def extract_asbuilt_batch(
    files: list[UploadFile] = File(...),
    map_to_catalog_flag: bool = Query(False, alias="map_to_catalog"),
    first_pages: int = 8,
    confidence_threshold: float = 0.75,
):
    run_id = str(uuid.uuid4())
    created_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    results: list[dict] = []

    for f in files:
        ct = f.content_type or "application/pdf"
        if ct not in ("application/pdf", "image/png", "image/jpeg"):
            results.append(
                {
                    "filename": f.filename,
                    "parsed": None,
                    "di_result": None,
                    "warnings": {},
                    "errors": [{"error": True, "stage": "input", "text": f"Unsupported content type: {ct}"}],
                }
            )
            continue

        raw = await f.read()
        di_result = await _analyze_with_retry(raw, ct, start_pages=first_pages)

        if isinstance(di_result, dict) and di_result.get("error"):
            results.append(
                {
                    "filename": f.filename,
                    "parsed": None,
                    "di_result": di_result,
                    "warnings": {},
                    "errors": [di_result],
                }
            )
            continue

        parsed = parse_asbuilt(di_result)
        flat_text = _flatten_read_text(di_result)

        extracted = parsed.get("extracted") or {}
        extracted = apply_library(flat_text, extracted)

        low = flag_low_confidence(extracted, threshold=confidence_threshold)

        parsed["extracted"] = extracted
        parsed.setdefault("warnings", {})
        parsed["warnings"]["low_confidence_fields"] = low
        parsed["filename"] = f.filename

        if map_to_catalog_flag:
            try:
                parsed["_catalog"] = map_to_catalog(
                    {
                        "filename": f.filename,
                        "_raw_text": flat_text,
                        "extracted": extracted,
                        "_extraction_meta": parsed.get("_extraction_meta", {}),
                        "warnings": parsed.get("warnings", {}),
                    },
                    load_field_catalog(),
                )
            except Exception as e:
                parsed.setdefault("warnings", {})
                parsed["warnings"]["catalog_mapping_error"] = str(e)

        results.append(
            {
                "filename": f.filename,
                "parsed": parsed,
                "di_result": di_result,
                "warnings": parsed.get("warnings", {}),
                "errors": [],
            }
        )

    output = build_output_v1(
        parsed_items=results,
        env=APP_ENV,
        run_id=run_id,
        created_utc=created_utc,
        )
    export_plants_to_csv(output, "debug_output.csv")

    return output


@app.post("/extract/asbuilt", tags=["extract"])
async def extract_asbuilt(file: UploadFile = File(...), first_pages: int = 8):
    ct = file.content_type or "application/pdf"
    if ct not in ("application/pdf", "image/png", "image/jpeg"):
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {ct}")

    raw = await file.read()
    result = await _analyze_with_retry(raw, ct, start_pages=first_pages)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=502, detail=result)

    parsed = parse_asbuilt(result)
    flat_text = _flatten_read_text(result)
    extracted = parsed.get("extracted") or {}
    parsed["extracted"] = apply_library(flat_text, extracted)
    parsed["filename"] = file.filename
    return parsed


@app.post("/export/catalog/batch", tags=["export"])
async def export_catalog_batch(
    files: List[UploadFile] = File(...),
    first_pages: int = 8,
    confidence_threshold: float = 0.75,
):
    cat = load_field_catalog()
    items: List[dict] = []

    for f in files:
        ct = f.content_type or "application/pdf"
        if ct not in ("application/pdf", "image/png", "image/jpeg"):
            items.append(
                {
                    "filename": f.filename,
                    "error": {"error": True, "stage": "input", "text": f"Unsupported content type: {ct}"},
                }
            )
            continue

        raw = await f.read()
        di_result = await _analyze_with_retry(raw, ct, start_pages=first_pages)
        if isinstance(di_result, dict) and di_result.get("error"):
            items.append({"filename": f.filename, "error": di_result})
            continue

        parsed = parse_asbuilt(di_result)
        flat_text = _flatten_read_text(di_result)

        extracted = parsed.get("extracted") or {}
        extracted = apply_library(flat_text, extracted)

        low = flag_low_confidence(extracted, threshold=confidence_threshold)

        item_for_mapper = {
            "filename": f.filename,
            "_raw_text": flat_text,
            "extracted": extracted,
            "_extraction_meta": parsed.get("_extraction_meta", {}),
            "warnings": {"low_confidence_fields": low},
        }

        try:
            catalog_payload = map_to_catalog(item_for_mapper, cat)
        except Exception as e:
            items.append(
                {
                    "filename": f.filename,
                    "error": {"error": True, "stage": "mapping", "text": str(e)},
                }
            )
            continue

        catalog_payload.setdefault("_meta", {})
        catalog_payload["_meta"]["filename"] = f.filename
        items.append(catalog_payload)

    return {"items": items}


@app.post("/export/catalog", tags=["export"])
async def export_catalog(
    file: UploadFile = File(...),
    first_pages: int = 8,
    confidence_threshold: float = 0.75,
):
    cat = load_field_catalog()

    ct = file.content_type or "application/pdf"
    if ct not in ("application/pdf", "image/png", "image/jpeg"):
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {ct}")

    raw = await file.read()
    di_result = await _analyze_with_retry(raw, ct, start_pages=first_pages)
    if isinstance(di_result, dict) and di_result.get("error"):
        raise HTTPException(status_code=502, detail=di_result)

    parsed = parse_asbuilt(di_result)
    flat_text = _flatten_read_text(di_result)

    extracted = parsed.get("extracted") or {}
    extracted = apply_library(flat_text, extracted)

    low = flag_low_confidence(extracted, threshold=confidence_threshold)

    item_for_mapper = {
        "filename": file.filename,
        "_raw_text": flat_text,
        "extracted": extracted,
        "_extraction_meta": parsed.get("_extraction_meta", {}),
        "warnings": {"low_confidence_fields": low},
    }

    catalog_payload = map_to_catalog(item_for_mapper, cat)
    catalog_payload.setdefault("_meta", {})
    catalog_payload["_meta"]["filename"] = file.filename
    return catalog_payload

@app.post("/preflight/native", tags=["preflight"])
async def preflight_native(
    file: UploadFile = File(...),
    max_pages: int = Query(25, ge=1, le=200),
):
    raw = await file.read()

    native = parse_native(
        filename=file.filename or "file",
        file_bytes=raw,
        max_pages=max_pages,
        include_blocks=False,
    )

    return build_preflight_summary(native)

@app.post("/scan/summary", tags=["scan"], response_model=SummaryResponse)
def scan_summary(req: SummaryRequest):
    try:
        return summarize_folder(
            root_path=req.root_path,
            sample_pages=req.sample_pages,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("scan-summary crashed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract/asbuilt-simple", tags=["extract"])
async def asbuilt_simple(file: UploadFile = File(...), first_pages: int = 3):
    try:
        result = await _run_read_ocr(file, first_pages=first_pages)

        flat_text = _flatten_read_text(result)
        if not flat_text:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "ocr_empty",
                    "hint": "DI returned no content, try increasing first_pages or use a different file",
                },
            )

        rules_path = find_rules_file()
        rules = load_rules_file(rules_path)

        data = extract_from_yaml(flat_text, rules)
        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("asbuilt-simple crashed")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace": traceback.format_exc().splitlines()[-15:]},
        )
