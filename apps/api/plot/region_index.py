"""Instant, offline search over all Polish cadastral precincts (obręby ewidencyjne).

Built by scripts/build_region_index.py from PRG (GUGiK). Why not ULDK: ULDK only
matches the *exact* obręb name, and many villages are split into several obręby
("Zdziłowice" → "Zdziłowice Pierwsze/Drugie/Czwarte"), so farmers typing the
village name got nothing. Here the search is:

* prefix + word-prefix ("zdzil" → all Zdziłowice …),
* diacritics/case/hyphen-insensitive ("lodz" → "Łódź"),
* by gmina too ("Godziszów" → every obręb in gmina Godziszów),
* optional narrowing after a comma: "Nowa Wieś, janowski" / "Zdziłowice, godzisz".
"""

from __future__ import annotations

import gzip
import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

INDEX_PATH = Path(__file__).resolve().parent / "data" / "regions_pl.json.gz"
MAX_RESULTS = 100

_EXTRA = str.maketrans({"ł": "l", "Ł": "l", "-": " ", ".": " ", "_": " "})


def norm(s: str | None) -> str:
    """'Zdziłowice-Kolonia' → 'zdzilowice kolonia'."""
    if not s:
        return ""
    s = s.translate(_EXTRA)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


@dataclass(frozen=True)
class Entry:
    region_id: str
    name: str
    commune: str | None
    county: str | None
    voivodeship: str | None
    n_name: str
    n_words: tuple[str, ...]
    n_commune: str
    n_where: str  # commune + county + voivodeship, for the comma filter

    def to_dict(self) -> dict[str, Any]:
        return {
            "regionId": self.region_id,
            "region": self.name,
            "commune": self.commune,
            "county": self.county,
            "voivodeship": self.voivodeship,
            "bbox": None,  # fetched lazily: GET /plot/region-extent
        }


def _commune_name(communes: dict[str, str], region_id: str) -> str | None:
    """'060504_2.0013' → gmina code '0605042'. Town/rural parts (_4/_5) belong to gmina _3."""
    base, kind = region_id[:6], region_id[7]
    for k in (kind, "3", "2", "1"):
        if f"{base}{k}" in communes:
            return communes[f"{base}{k}"]
    return None


@lru_cache(maxsize=1)
def load_index() -> tuple[Entry, ...]:
    """Empty tuple if the index file is missing (caller falls back to ULDK)."""
    if not INDEX_PATH.exists():
        return ()
    with gzip.open(INDEX_PATH, "rt", encoding="utf-8") as f:
        data = json.load(f)
    voiv, counties, communes = data["voivodeships"], data["counties"], data["communes"]
    out: list[Entry] = []
    for rid, name in data["regions"]:
        commune = _commune_name(communes, rid)
        county = counties.get(rid[:4])
        v = voiv.get(rid[:2])
        n_name = norm(name)
        out.append(Entry(
            region_id=rid, name=name, commune=commune, county=county, voivodeship=v,
            n_name=n_name, n_words=tuple(n_name.split()), n_commune=norm(commune),
            n_where=norm(" ".join(filter(None, (commune, county, v)))),
        ))
    return tuple(out)


def _score(e: Entry, q: str, q_words: list[str]) -> int | None:
    """Lower = better. None = no match."""
    if e.n_name == q:
        return 0
    if e.n_name.startswith(q):
        return 1
    # every query word is a prefix of some name word: "pierwsze zdzil" → "Zdziłowice Pierwsze"
    if all(any(w.startswith(qw) for w in e.n_words) for qw in q_words):
        return 2
    if e.n_commune == q:
        return 3  # whole gmina listed
    if e.n_commune.startswith(q) and len(q) >= 4:
        return 4
    return None


def search(query: str) -> tuple[list[dict[str, Any]], int]:
    """Returns (best matches, total match count). `query` may contain ', filter'."""
    entries = load_index()
    name_part, _, where_part = (query or "").partition(",")
    q = norm(name_part)
    if not q:
        return [], 0
    q_words = q.split()
    where_words = norm(where_part).split()

    hits: list[tuple[int, Entry]] = []
    for e in entries:
        s = _score(e, q, q_words)
        if s is None:
            continue
        if where_words and not all(w in e.n_where for w in where_words):
            continue
        hits.append((s, e))
    hits.sort(key=lambda h: (h[0], h[1].n_name, h[1].voivodeship or "", h[1].county or "", h[1].region_id))
    return [e.to_dict() for _, e in hits[:MAX_RESULTS]], len(hits)
