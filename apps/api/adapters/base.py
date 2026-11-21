"""Shared adapter wrapper: uniform response shape, disk cache, hard timeout, fail-soft.

Every data adapter (Open-Meteo, SoilGrids, DEM, hydro, Sentinel-2, drought) should
call `run_adapter(...)` and return its result unchanged. The wrapper guarantees:

* the same response shape for every source (`AdapterResponse.model_dump()`),
* a hard timeout (default 20 s) around the network work,
* no exception ever escapes (errors land in `errors`, `coverage="none"`),
* deterministic disk cache keyed by source name + input params; only fully
  successful responses are cached, never errors / timeouts / partial results.

Contract for `fetch_fn`:
    async def fetch() -> dict[str, Any]            # full success -> values dict
    async def fetch() -> PartialResult              # some sub-requests failed

Remember to include the analysis date / date range in `cache_key_data`: the jury
may request historical analysis dates, so cache entries must be date-specific.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

import httpx
from pydantic import BaseModel, Field

Coverage = Literal["full", "partial", "none"]

CACHE_DIR = Path(
    os.environ.get("ADAPTER_CACHE_DIR", Path(__file__).resolve().parent.parent / "cache")
)
DEFAULT_TIMEOUT_SEC = 20.0

# Shared deadline (time.monotonic()) for every adapter started inside `adapter_deadline()`.
# A ContextVar, so tasks created by asyncio.gather inherit it.
_deadline: ContextVar[float | None] = ContextVar("adapter_deadline", default=None)


@contextmanager
def adapter_deadline(seconds: float):
    """All `run_adapter` calls in this block finish within `seconds` (cache hits always pass)."""
    token = _deadline.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def _effective_timeout(timeout_sec: float) -> tuple[float, bool]:
    """(timeout to use, True if it was cut by the shared deadline)."""
    dl = _deadline.get()
    if dl is None:
        return timeout_sec, False
    left = dl - time.monotonic()
    return (left, True) if left < timeout_sec else (timeout_sec, False)


# --------------------------------------------------------------------------- models


class SourceRef(BaseModel):
    name: str
    url: str
    fetchedAt: str


class AdapterResponse(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    fetchedAt: str
    coverage: Coverage
    errors: list[str] = Field(default_factory=list)
    fromCache: bool = False


@dataclass
class PartialResult:
    """Return this from `fetch_fn` when only part of the data could be fetched.

    `definitive=True` marks a *stable* negative answer that is not a failure – e.g.
    "no cloud-free satellite scene existed for this historical date". Such results
    may be cached; transient failures (timeouts, HTTP errors) never are.
    """

    values: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    definitive: bool = False


# --------------------------------------------------------------------------- helpers


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_cache_key(source_name: str, cache_key_data: dict[str, Any]) -> str:
    """Deterministic SHA-256 of source name + sorted-JSON params."""
    payload = json.dumps(
        {"source": source_name, "params": cache_key_data},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,  # dates, Paths, etc.
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(source_name: str, key: str, cache_dir: Path) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in source_name)
    return cache_dir / safe / f"{key}.json"


def _read_cache(path: Path, ttl_sec: float | None) -> AdapterResponse | None:
    try:
        if not path.is_file():
            return None
        if ttl_sec is not None:
            age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
            if age > ttl_sec:
                return None
        data = json.loads(path.read_text(encoding="utf-8"))
        resp = AdapterResponse.model_validate(data)
        resp.fromCache = True
        return resp
    except Exception:  # corrupt / unreadable cache -> treat as miss
        return None


def _write_cache(path: Path, resp: AdapterResponse) -> None:
    """Atomic write (temp file + rename) so concurrent readers never see half a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = resp.model_copy(update={"fromCache": False}).model_dump_json(indent=2)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, path)
    except Exception:
        pass  # cache is best-effort; never fail the request because of it


def _describe_error(exc: BaseException, timeout_sec: float) -> str:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return f"Przekroczono limit czasu ({timeout_sec:.0f} s) – źródło nie odpowiedziało."
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Błąd HTTP {exc.response.status_code} z {exc.request.url.host}."
    if isinstance(exc, httpx.TimeoutException):
        return "Przekroczono limit czasu połączenia HTTP."
    if isinstance(exc, httpx.HTTPError):
        return f"Błąd połączenia HTTP: {type(exc).__name__}: {exc}"
    return f"Nieoczekiwany błąd adaptera: {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- main API


async def run_adapter(
    source_name: str,
    source_url: str,
    cache_key_data: dict[str, Any],
    fetch_fn: Callable[[], Awaitable[dict[str, Any] | PartialResult]],
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    *,
    cache_ttl_sec: float | None = None,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Run one source fetch with cache + hard timeout. Never raises.

    `cache_ttl_sec=None` caches forever (fine for historical ranges); pass a TTL
    for data that changes (e.g. ranges ending today).
    """
    cdir = cache_dir or CACHE_DIR
    try:
        path = _cache_path(source_name, make_cache_key(source_name, cache_key_data), cdir)
        cached = _read_cache(path, cache_ttl_sec)
        if cached is not None:
            return cached.model_dump()
    except Exception:
        path = None

    now = utc_now_iso()
    source = SourceRef(name=source_name, url=source_url, fetchedAt=now)

    timeout, cut_by_deadline = _effective_timeout(timeout_sec)
    budget_msg = "Zabrakło czasu w budżecie analizy (cel < 30 s) – źródło pominięte lub przerwane."
    if timeout <= 0.2:
        return AdapterResponse(
            values={}, sources=[source], fetchedAt=now, coverage="none", errors=[budget_msg]
        ).model_dump()

    try:
        result = await asyncio.wait_for(fetch_fn(), timeout=timeout)
    except BaseException as exc:  # noqa: BLE001 – fail-soft by contract
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, asyncio.CancelledError) and not isinstance(exc, asyncio.TimeoutError):
            # Outer task cancelled (e.g. client disconnect) – still answer, never crash.
            pass
        timed_out = isinstance(exc, (asyncio.TimeoutError, TimeoutError))
        return AdapterResponse(
            values={},
            sources=[source],
            fetchedAt=now,
            coverage="none",
            errors=[budget_msg if timed_out and cut_by_deadline else _describe_error(exc, timeout)],
        ).model_dump()

    try:
        if isinstance(result, PartialResult):
            values, errors = dict(result.values), list(result.errors)
        elif isinstance(result, dict):
            values, errors = result, []
        else:
            values, errors = {}, [f"Adapter zwrócił nieprawidłowy typ: {type(result).__name__}"]

        if not values:
            coverage: Coverage = "none"
            errors = errors or ["Źródło nie zwróciło żadnych danych."]
        elif errors:
            coverage = "partial"
        else:
            coverage = "full"

        resp = AdapterResponse(
            values=values, sources=[source], fetchedAt=now, coverage=coverage, errors=errors
        )
        payload = resp.model_dump()  # validates JSON-serialisable shape early
        definitive = isinstance(result, PartialResult) and result.definitive
        if (coverage == "full" or definitive) and path is not None:
            _write_cache(path, resp)
        return payload
    except Exception as exc:  # e.g. non-serialisable values
        return AdapterResponse(
            values={},
            sources=[source],
            fetchedAt=now,
            coverage="none",
            errors=[_describe_error(exc, timeout_sec)],
        ).model_dump()


# --------------------------------------------------------------------------- demo

if __name__ == "__main__":
    import time

    async def _demo() -> None:
        demo_dir = Path(tempfile.mkdtemp(prefix="adapter-cache-demo-"))
        key = {"lat": 52.23, "lon": 21.01, "start": "2016-11-21", "end": "2026-11-21"}

        calls = 0

        async def fast_fetch() -> dict[str, Any]:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.5)
            return {"precip_sum_mm": 5432.1, "dry_spells": 17}

        async def hanging_fetch() -> dict[str, Any]:
            await asyncio.sleep(25)
            return {"never": True}

        t = time.perf_counter()
        r1 = await run_adapter("demo-fast", "https://example.org", key, fast_fetch, cache_dir=demo_dir)
        print(f"1st call  {time.perf_counter() - t:5.2f}s  fromCache={r1['fromCache']} coverage={r1['coverage']}")
        assert not r1["fromCache"] and r1["coverage"] == "full"

        t = time.perf_counter()
        r2 = await run_adapter("demo-fast", "https://example.org", key, fast_fetch, cache_dir=demo_dir)
        print(f"2nd call  {time.perf_counter() - t:5.2f}s  fromCache={r2['fromCache']} values={r2['values']}")
        assert r2["fromCache"] and r2["values"] == r1["values"] and calls == 1

        print("hanging call (expect ~20s timeout)...")
        t = time.perf_counter()
        r3 = await run_adapter("demo-hang", "https://example.org", key, hanging_fetch, cache_dir=demo_dir)
        print(f"hang call {time.perf_counter() - t:5.2f}s  coverage={r3['coverage']} errors={r3['errors']}")
        assert r3["coverage"] == "none" and r3["values"] == {}
        assert not (demo_dir / "demo-hang").exists(), "timeouts must never be cached"

        print("OK – cache dir:", demo_dir)

    asyncio.run(_demo())
