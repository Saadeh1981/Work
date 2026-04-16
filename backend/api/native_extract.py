from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.native_parser_router import parse_native

router = APIRouter(prefix="/extract", tags=["extract"])


class NativeExtractRequest(BaseModel):
    file_path: str


@router.post("/native")
def extract_native(req: NativeExtractRequest) -> dict:
    try:
        result = parse_native(path=req.file_path, file_bytes=None)
        if result["file_type"] == "other":
            raise HTTPException(status_code=415, detail="Unsupported file type")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
