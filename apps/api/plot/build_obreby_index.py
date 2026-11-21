"""Build the offline index of cadastral precincts (obręby ewidencyjne) for village search.

Why: ULDK only finds an obręb by its exact full name (with Polish letters). Farmers type
"Zolwin" or "Krzew…", so we keep a local list of all ~54k obręby names (no geometry) and
match them diacritic-insensitively / by prefix. Geometry (bbox) and plots still come live
from ULDK.

Source: PRG (Państwowy Rejestr Granic), GUGiK WFS "AdministrativeBoundaries" — open data.
Layers: A06 obręby, A03 gminy, A02 powiaty, A01 województwa (attributes only).

Usage (from apps/api):
    .venv/bin/python -m plot.build_obreby_index            # download (~3-4 min) + build
    .venv/bin/python -m plot.build_obreby_index --from DIR # use already downloaded <layer>.xml
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

WFS_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
LAYERS = {
    "regions": "A06_Granice_obrebow_ewidencyjnych",
    "communes": "A03_Granice_gmin",
    "counties": "A02_Granice_powiatow",
    "voivodeships": "A01_Granice_wojewodztw",
}
OUT = Path(__file__).parent / "data" / "obreby.json.gz"

_REC_RE = re.compile(
    r"<ms:JPT_KOD_JE>([^<]*)</ms:JPT_KOD_JE>\s*<ms:JPT_NAZWA_>([^<]*)</ms:JPT_NAZWA_>"
)
_ROMAN = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"}


def _fetch_layer(layer: str) -> str:
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": f"ms:{layer}",
        "PROPERTYNAME": "JPT_KOD_JE,JPT_NAZWA_",
    }
    r = httpx.get(WFS_URL, params=params, timeout=httpx.Timeout(600.0, connect=20.0))
    r.raise_for_status()
    return r.text


def _records(xml: str) -> list[tuple[str, str]]:
    return [(code.strip(), " ".join(name.split())) for code, name in _REC_RE.findall(xml)]


def nice_case(name: str) -> str:
    """'STARA WIEŚ-KOLONIA II' -> 'Stara Wieś-Kolonia II'. Mixed-case names are kept as is."""
    if not name.isupper():
        return name

    def word(w: str) -> str:
        return w if w in _ROMAN else w[:1] + w[1:].lower()

    return re.sub(r"[^\s\-()]+", lambda m: word(m.group(0)), name)


def build(xml_by_key: dict[str, str]) -> dict:
    regions = []
    for rid, name in _records(xml_by_key["regions"]):
        if not re.fullmatch(r"\d{6}_\d\.\d{4}", rid):
            continue
        # Urban precincts named only by number ("150", "1-05-03") are useless for name search.
        if not re.search(r"[^\W\d_]", name):
            continue
        regions.append([rid, nice_case(name)])
    regions.sort()
    return {
        "source": "PRG – Państwowy Rejestr Granic (GUGiK), usługa WFS AdministrativeBoundaries",
        "sourceUrl": WFS_URL,
        "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "voivodeships": dict(_records(xml_by_key["voivodeships"])),
        "counties": dict(_records(xml_by_key["counties"])),
        "communes": dict(_records(xml_by_key["communes"])),
        "regions": regions,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", type=Path, help="directory with <layer>.xml files")
    args = ap.parse_args()

    xml_by_key: dict[str, str] = {}
    for key, layer in LAYERS.items():
        if args.src:
            xml_by_key[key] = (args.src / f"{layer}.xml").read_text(encoding="utf-8")
        else:
            print(f"Pobieram {layer}…", file=sys.stderr)
            xml_by_key[key] = _fetch_layer(layer)

    index = build(xml_by_key)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    print(
        f"Zapisano {OUT} – obręby: {len(index['regions'])}, gminy: {len(index['communes'])}, "
        f"powiaty: {len(index['counties'])}, województwa: {len(index['voivodeships'])}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
