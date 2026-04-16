from __future__ import annotations

import json
from pathlib import Path

from backend.schemas.summary import SummaryResponse
from backend.services.pipeline_runner import build_pipeline_output


def main() -> None:
    summary_path = Path("data/sample_summary.json")

    if not summary_path.exists():
        print(f"Summary file not found: {summary_path}")
        return

    with open(summary_path, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    summary = SummaryResponse(**summary_data)

    output = build_pipeline_output(
        summary=summary,
        env="dev",
        run_id="test-run-001",
        created_utc="2026-03-12T12:00:00Z",
    )

    print(output.model_dump_json(indent=2))


if __name__ == "__main__":
    main()