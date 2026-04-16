import argparse
import asyncio
import json
from pathlib import Path

from backend.services.docint_client import DocumentIntelligenceClient
from backend.services.table_extractors.combiners_strings import (
    extract_combiners_strings,
    write_two_col_csv,
)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--save-json", default=None)
    args = p.parse_args()

    pdf_path = Path(args.pdf)
    raw = pdf_path.read_bytes()

    async def run():
        di = DocumentIntelligenceClient()
        res = await di.analyze_layout(raw, content_type="application/pdf")
        if isinstance(res, dict) and res.get("error"):
            raise RuntimeError(json.dumps(res, indent=2))

        if args.save_json:
            Path(args.save_json).write_text(
                json.dumps(res, indent=2),
                encoding="utf-8"
            )

        rows = extract_combiners_strings(res)

        print("rows:", len(rows))
        print("writing to:", args.out)

        write_two_col_csv(rows, args.out)

        print(f"Wrote {len(rows)} rows to {args.out}")

    asyncio.run(run())

if __name__ == "__main__":
    main()