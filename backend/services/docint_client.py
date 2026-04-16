# backend/services/docint_client.py
from __future__ import annotations

import os
import asyncio
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

PRIMARY_PATH = "documentintelligence"
PRIMARY_API = "2024-07-31"

FALLBACK_PATH = "formrecognizer"
FALLBACK_API = "2023-07-31"

READ_MODEL = "prebuilt-read"
LAYOUT_MODEL = "prebuilt-layout"

DEFAULT_TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=30.0)

# Polling controls
POLL_MAX_SECONDS = int(os.getenv("DOCINT_POLL_MAX_SECONDS", "900"))  # 15 minutes
POLL_SLEEP_SECONDS = float(os.getenv("DOCINT_POLL_SLEEP_SECONDS", "1.0"))
POLL_MIN_SLEEP_SECONDS = float(os.getenv("DOCINT_POLL_MIN_SLEEP_SECONDS", "0.5"))
POLL_MAX_SLEEP_SECONDS = float(os.getenv("DOCINT_POLL_MAX_SLEEP_SECONDS", "5.0"))


class DocumentIntelligenceClient:
    def __init__(self, endpoint: str | None = None, key: str | None = None):
        self.endpoint = (endpoint or os.getenv("DOCINT_ENDPOINT") or "").rstrip("/")
        self.key = (key or os.getenv("DOCINT_KEY") or "").strip()

        self.prefer = (os.getenv("DOCINT_PREFER") or "auto").strip().lower()
        # allowed: auto, documentintelligence, formrecognizer
        if self.prefer not in ("auto", "documentintelligence", "formrecognizer"):
            self.prefer = "auto"

        if not self.endpoint or not self.key:
            raise RuntimeError("Missing DOCINT_ENDPOINT or DOCINT_KEY")

    def _headers(self, content_type: str) -> dict:
        return {"Ocp-Apim-Subscription-Key": self.key, "Content-Type": content_type}

    def _flatten_error(self, body):
        code = msg = inner_code = inner_msg = None
        if isinstance(body, dict):
            err = body.get("error") or {}
            code = err.get("code") or body.get("code")
            msg = err.get("message") or body.get("message")
            inner = err.get("innererror") or {}
            inner_code = inner.get("code")
            inner_msg = inner.get("message")

        flat_code = inner_code or code

        error_kind = "size_limit" if (
            (flat_code and "InvalidContentLength" in str(flat_code))
            or (msg and "too large" in str(msg).lower())
            or (inner_msg and "too large" in str(inner_msg).lower())
        ) else None

        return flat_code, (msg or inner_msg), error_kind

    def _error_payload(self, stage: str, resp: httpx.Response) -> dict:
        try:
            body = resp.json()
        except Exception:
            body = resp.text

        flat_code, flat_msg, error_kind = self._flatten_error(body if isinstance(body, dict) else {})
        return {
            "error": True,
            "stage": stage,
            "status_code": resp.status_code,
            "code": flat_code,
            "message": flat_msg,
            "text": body,
            "error_kind": error_kind,
            "url": str(resp.request.url),
        }

    def _missing_op_location(self, resp: httpx.Response) -> dict:
        return {
            "error": True,
            "stage": "submit",
            "text": "Missing Operation-Location header",
            "status_code": resp.status_code,
            "url": str(resp.request.url),
        }

    def _parse_retry_after(self, resp: httpx.Response) -> Optional[float]:
        ra = resp.headers.get("Retry-After")
        if not ra:
            return None
        try:
            return float(ra)
        except Exception:
            return None

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict,
        headers: dict,
        content: bytes,
        max_attempts: int = 6,
    ) -> httpx.Response:
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.post(url, params=params, headers=headers, content=content)

                # Retry common transient statuses
                if resp.status_code in (408, 429, 500, 502, 503, 504):
                    ra = self._parse_retry_after(resp)
                    sleep_s = ra if ra is not None else min(2 ** attempt, 20)
                    await asyncio.sleep(sleep_s)
                    continue

                return resp

            except (
                httpx.WriteTimeout,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                httpx.RemoteProtocolError,
            ) as e:
                last_exc = e
                await asyncio.sleep(min(2 ** attempt, 20))

        if last_exc is not None:
            raise last_exc

        raise RuntimeError("Submit failed after retries")

    async def _submit_model(
        self,
        client: httpx.AsyncClient,
        path: str,
        api: str,
        model: str,
        content: bytes,
        content_type: str,
    ) -> httpx.Response:
        url = f"{self.endpoint}/{path}/documentModels/{model}:analyze"
        return await self._post_with_retries(
            client,
            url,
            params={"api-version": api},
            headers=self._headers(content_type),
            content=content,
        )

    async def _poll(self, client: httpx.AsyncClient, op_url: str) -> dict:
        headers = {"Ocp-Apim-Subscription-Key": self.key}

        elapsed = 0.0
        sleep_s = POLL_SLEEP_SECONDS

        while elapsed < float(POLL_MAX_SECONDS):
            try:
                pr = await client.get(op_url, headers=headers)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                sleep_s = max(float(POLL_MIN_SLEEP_SECONDS), min(float(POLL_MAX_SLEEP_SECONDS), float(sleep_s) * 1.5))
                await asyncio.sleep(sleep_s)
                elapsed += sleep_s
                continue

            if pr.status_code >= 400:
                return self._error_payload("poll", pr)

            data = pr.json() if pr.content else {}
            status = (data or {}).get("status")

            if status in ("succeeded", "failed", "canceled"):

                from pathlib import Path
                import json
                import os

                out_path = Path.cwd() / "out" / "debug_layout.json"
                out_path.parent.mkdir(parents=True, exist_ok=True)

                with out_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                print(f"Saved DI result to {out_path}")
                print(f"Current working directory: {os.getcwd()}")
                print("DOCINT _poll reached")

                return data

            ra = self._parse_retry_after(pr)
            if ra is not None:
                sleep_s = ra

            sleep_s = max(float(POLL_MIN_SLEEP_SECONDS), min(float(POLL_MAX_SLEEP_SECONDS), float(sleep_s)))
            await asyncio.sleep(sleep_s)
            elapsed += sleep_s

        return {
            "error": True,
            "stage": "poll",
            "text": f"Timeout waiting for analysis after {POLL_MAX_SECONDS}s",
            "url": op_url,
        }

    async def _analyze_model(self, model: str, file_bytes: bytes, content_type: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                if self.prefer == "formrecognizer":
                    resp = await self._submit_model(client, FALLBACK_PATH, FALLBACK_API, model, file_bytes, content_type)
                elif self.prefer == "documentintelligence":
                    resp = await self._submit_model(client, PRIMARY_PATH, PRIMARY_API, model, file_bytes, content_type)
                else:
                    resp = await self._submit_model(client, PRIMARY_PATH, PRIMARY_API, model, file_bytes, content_type)
                    if resp.status_code == 404 or ("Resource not Found" in resp.text) or ("Resource Not Found" in resp.text):
                        resp = await self._submit_model(client, FALLBACK_PATH, FALLBACK_API, model, file_bytes, content_type)

                if resp.status_code >= 400:
                    return self._error_payload("submit", resp)

                op_url = resp.headers.get("operation-location") or resp.headers.get("Operation-Location")
                if not op_url:
                    return self._missing_op_location(resp)

                return await self._poll(client, op_url)
        except Exception as e:
            return {"error": True, "stage": "exception", "text": repr(e)}

    async def analyze_read(self, file_bytes: bytes, content_type: str = "application/pdf") -> dict:
        """
        Calls prebuilt-read (OCR + text).
        """
        return await self._analyze_model(READ_MODEL, file_bytes, content_type)

    async def analyze_layout(self, file_bytes: bytes, content_type: str = "application/pdf") -> dict:
        """
        Calls prebuilt-layout (tables + cells).
        """
        return await self._analyze_model(LAYOUT_MODEL, file_bytes, content_type)