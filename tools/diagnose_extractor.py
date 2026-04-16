#!/usr/bin/env python3
"""
Diagnose extractor outputs for a given PDF.

- Calls /extract/asbuilt and saves JSON to out\debug_asbuilt.json
- Calls /extract/read-test and saves text to out\debug_readtest.txt
- Prints basic stats (text length, first 40 lines preview)

Usage:
python diagnose_extractor.py ^
  --input ".\inputs\your.pdf" ^
  --api-struct "http://127.0.0.1:8000/extract/asbuilt" ^
  --api-ocr "http://127.0.0.1:8000/extract/read-test" ^
  --first-pages 12
"""
import argparse, json
from pathlib import Path
import sys

try:
    import requests
except ImportError:
    import httpx as requests  # type: ignore

def post_file(api: str, pdf: Path, first_pages: int):
    files = {"file": (pdf.name, open(pdf, "rb"), "application/pdf")}
    params = {"first_pages": first_pages}
    try:
        r = requests.post(api, files=files, params=params, timeout=300)
    finally:
        try: files["file"][1].close()
        except Exception: pass
    return r

def extract_text(obj):
    if isinstance(obj, dict):
        # common keys
        for k in ["text","full_text","content","ocr","raw_text"]:
            if k in obj and isinstance(obj[k], str):
                return obj[k]
        # stitch strings and lists of strings
        parts = []
        for v in obj.values():
            if isinstance(v, str): parts.append(v)
            elif isinstance(v, list): parts += [x for x in v if isinstance(x, str)]
        return "\n".join(parts)
    return str(obj)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--api-struct", default="http://127.0.0.1:8000/extract/asbuilt")
    ap.add_argument("--api-ocr", default="http://127.0.0.1:8000/extract/read-test")
    ap.add_argument("--first-pages", type=int, default=12)
    ap.add_argument("--outdir", default=".\\out")
    args = ap.parse_args()

    pdf = Path(args.input).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # Structured
    r1 = post_file(args.api_struct, pdf, args.first_pages)
    try:
        j1 = r1.json()
    except Exception:
        j1 = {"status": r1.status_code, "text": r1.text[:500]}
    (outdir/"debug_asbuilt.json").write_text(json.dumps(j1, indent=2), encoding="utf-8")
    print(f"[asbuilt] HTTP {r1.status_code}, saved -> {outdir/'debug_asbuilt.json'}")

    # OCR
    r2 = post_file(args.api_ocr, pdf, args.first_pages)
    try:
        j2 = r2.json()
    except Exception:
        j2 = r2.text
    text = extract_text(j2)
    (outdir/"debug_readtest.txt").write_text(text, encoding="utf-8")
    lines = [l for l in text.splitlines() if l.strip()]
    print(f"[read-test] HTTP {r2.status_code}, text_len={len(text)}, nonempty_lines={len(lines)}")
    print("---- preview (first 40 lines) ----")
    for line in lines[:40]:
        print(line)
    print("---- end preview ----")

if __name__ == "__main__":
    main()
