"""Build the offline index of all Polish cadastral precincts (obręby ewidencyjne).

Source: PRG (Państwowy Rejestr Granic), GUGiK WFS "AdministrativeBoundaries" — open data.
Layers: A06 obręby, A03 gminy, A02 powiaty, A01 województwa (codes + names only, no geometry).

Output: plot/data/regions_pl.json.gz, read by plot/region_index.py for instant local search
(prefix, no diacritics needed, by gmina name). Re-run when PRG changes (rarely):

    cd apps/api && python scripts/build_region_index.py
"""

from __future__ import annotations

import gzip
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

WFS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
PAGE = 10_000
OUT = Path(__file__).resolve().parent.parent / "plot" / "data" / "regions_pl.json.gz"

_MEMBER_RE = re.compile(
    r"<ms:JPT_KOD_JE>([^<]*)</ms:JPT_KOD_JE>\s*<ms:JPT_NAZWA_>([^<]*)</ms:JPT_NAZWA_>"
)
_ROMAN_RE = re.compile(r"\b(?=[ivxlc]+\b)([ivxlc]+)\b", re.IGNORECASE)


def _fetch(layer: str, start: int) -> list[tuple[str, str]]:
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": f"ms:{layer}", "COUNT": str(PAGE), "STARTINDEX": str(start),
        "PROPERTYNAME": "JPT_KOD_JE,JPT_NAZWA_",
    }
    url = f"{WFS}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Retencja-DSS/region-index"})
            with urllib.request.urlopen(req, timeout=180) as r:
                text = r.read().decode("utf-8")
            return [(html.unescape(k).strip(), html.unescape(n).strip()) for k, n in _MEMBER_RE.findall(text)]
        except Exception as exc:  # noqa: BLE001
            print(f"  {layer} @{start}: {exc} (retry {attempt + 1})", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"WFS failed for {layer} @{start}")


def _fetch_all(layer: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    start = 0
    while True:
        page = _fetch(layer, start)
        out.extend(page)
        print(f"  {layer}: {len(out)}")
        if len(page) < PAGE:
            return out
        start += PAGE


def _pretty(name: str) -> str:
    """'ZDZIŁOWICE PIERWSZE' → 'Zdziłowice Pierwsze', keeps roman numerals ('… II')."""
    if not name.isupper():
        return name
    s = name.title()
    return _ROMAN_RE.sub(lambda m: m.group(1).upper(), s)


def main() -> None:
    print("PRG WFS → region index")
    voiv = dict(_fetch_all("A01_Granice_wojewodztw"))
    powiat = dict(_fetch_all("A02_Granice_powiatow"))
    gmina = dict(_fetch_all("A03_Granice_gmin"))
    raw = _fetch_all("A06_Granice_obrebow_ewidencyjnych")

    regions = sorted({k: _pretty(n) for k, n in raw if re.match(r"^\d{6}_\d\.\d{4}$", k)}.items())
    data = {
        "source": "PRG – Państwowy Rejestr Granic (GUGiK), WFS AdministrativeBoundaries",
        "builtAt": date.today().isoformat(),
        "voivodeships": voiv,   # "06" → "lubelskie"
        "counties": powiat,     # "0605" → "powiat janowski"
        "communes": gmina,      # "0605042" → "Godziszów"
        "regions": regions,     # [["060504_2.0013", "Zdziłowice Pierwsze"], ...]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(regions)} obrębów, {len(gmina)} gmin → {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
