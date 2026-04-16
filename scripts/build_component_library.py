from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pvlib import pvsystem
import os
if os.getenv("ALLOW_LIBRARY_REBUILD") != "1":
    raise RuntimeError("Component library rebuild is locked. Set ALLOW_LIBRARY_REBUILD=1 to override.")


OUT_DIR = Path("backend/data/component_library")


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].astype(str)
    df.index = df.index.astype(str)
    return df


def save_df(df: pd.DataFrame, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = normalize_df(df)
    df.to_parquet(OUT_DIR / f"{name}.parquet", index=True)


def main() -> None:
    cec_modules = pvsystem.retrieve_sam("CECMod")
    cec_inverters = pvsystem.retrieve_sam("cecinverter")
    sandia_inverters = pvsystem.retrieve_sam("sandiainverter")
    sandia_modules = pvsystem.retrieve_sam("sandiamod")

    save_df(cec_modules, "cec_modules")
    save_df(cec_inverters, "cec_inverters")
    save_df(sandia_inverters, "sandia_inverters")
    save_df(sandia_modules, "sandia_modules")

    meta = {
        "sources": [
            "pvlib.retrieve_sam: CECMod",
            "pvlib.retrieve_sam: cecinverter",
            "pvlib.retrieve_sam: sandiainverter",
            "pvlib.retrieve_sam: sandiamod",
        ],
        "row_counts": {
            "cec_modules": len(cec_modules),
            "cec_inverters": len(cec_inverters),
            "sandia_inverters": len(sandia_inverters),
            "sandia_modules": len(sandia_modules),
        },
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    }

    (OUT_DIR / "meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
