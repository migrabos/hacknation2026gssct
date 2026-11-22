"""Land use of a cadastral plot (pole, łąka, pastwisko, sad, las, siedlisko …) – ONLY from
the official land register (EGiB). Nothing is inferred from satellites or heuristics.

Source: GUGiK *Krajowa Integracja Ewidencji Gruntów* (WMS GetFeatureInfo, layer `kontury`).
One point inside the plot returns the parcel record with *all* its land-use contours
(no per-contour areas), e.g. ``RIIIa`` (grunt orny, klasa IIIa), ``ŁIV`` (łąka),
``PsV`` (pastwisko), ``LsVI`` (las), ``Br/RIVa`` (grunty rolne zabudowane – siedlisko).

Rules (truth over completeness):
  * one use in the register       → that use
  * several uses                  → "mixed" + the full list (register gives no areas,
                                     so we do not pick a "main" one)
  * contours not published / service down / other parcel returned → category None
    ("brak danych") with the reason

    landUse = {
      category, labelPl, isAgricultural (True/False/None = unknown), source: "egib"|None,
      uses: [labelPl…], codes: ["RIIIa", …], soilClasses: ["IIIa", …],
      egib: {codes:[{code, category, soilClass}], published, parcelAreaHa, dataDate} | None,
      notes: [str]
    }
"""

from __future__ import annotations

import html
import re
from typing import Any

import httpx
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from adapters.base import PartialResult, run_adapter

KIEG_URL = "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow"
KIEG_SOURCE = "KIEG GUGiK – EGiB użytki gruntowe"

DAY = 86_400
CACHE_TTL = 7 * DAY  # register changes rarely
TIMEOUT_SEC = 10.0  # KIEG cascades to the county server; some answer in 5–8 s

# --------------------------------------------------------------------------- categories

LABEL_PL: dict[str, str] = {
    "arable": "grunt orny (pole uprawne)",
    "meadow": "łąka trwała",
    "pasture": "pastwisko trwałe",
    "orchard": "sad",
    "farmyard": "siedlisko (zabudowane grunty rolne)",
    "forest": "las",
    "woodland": "zadrzewienia lub zakrzewienia",
    "built": "teren zabudowany",
    "transport": "droga lub teren kolejowy",
    "water": "woda (staw, rów, ciek)",
    "wetland": "teren podmokły",
    "bare": "nieużytek / teren bez roślinności",
    "other": "inny użytek",
    "mixed": "kilka użytków (mieszane)",
}
# Uses on which a crop / grassland water report makes sense (pole, łąka, pastwisko, sad).
AGRICULTURAL = {"arable", "meadow", "pasture", "orchard"}

# EGiB land-use symbols (rozporządzenie w sprawie EGiB, zał. 6) → category.
EGIB_USE: dict[str, str] = {
    "R": "arable", "Ł": "meadow", "Ps": "pasture", "S": "orchard",
    "Br": "farmyard", "Wsr": "water", "W": "water", "Lzr": "woodland",
    "Ls": "forest", "Lz": "woodland",
    "B": "built", "Ba": "built", "Bi": "built", "Bp": "built", "Bz": "built", "K": "built",
    "dr": "transport", "Tk": "transport", "Ti": "transport", "Tp": "transport", "Tr": "transport",
    "Wm": "water", "Wp": "water", "Ws": "water",
    "N": "bare",
}
_EGIB_CODE_RE = re.compile(r"^(?P<use>[A-Za-zŁłŚśŻż]+?)(?P<cls>(?:VI|IV|V|III|II|I)(?:a|b|z)?)?$")

def parse_egib_code(raw: str) -> dict[str, Any] | None:
    """One contour code: 'RIIIa' → arable/IIIa; 'Br-RIVa' or 'Br/RIVa' → farmyard/IVa; '' → None."""
    code = (raw or "").strip()
    if not code or code.lower() == "null":
        return None
    use_part, _, contour = code.replace("/", "-").partition("-")
    if use_part == "E" and contour:  # użytek ekologiczny, e.g. E-ŁIV → judge by the contour
        use_part, contour = contour, ""
    m = _EGIB_CODE_RE.match(use_part)
    sym, soil = (m.group("use"), m.group("cls")) if m else (use_part, None)
    if contour:  # 'Br-RIVa' / 'S-RIIIb': soil class sits in the second part
        cm = _EGIB_CODE_RE.match(contour)
        soil = soil or (cm.group("cls") if cm else None)
    return {"code": code, "category": EGIB_USE.get(sym, "other"), "soilClass": soil}


def parse_egib_codes(raw: str) -> list[dict[str, Any]]:
    """KIEG lists *all* contours of the parcel, comma-separated: 'RIIIb,RIVa,PsIII,Br/RIVa'."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        c = parse_egib_code(part)
        if c and c["code"] not in seen:
            seen.add(c["code"])
            out.append(c)
    return out


# --------------------------------------------------------------------------- EGiB (KIEG)


def _attrs(xml: str) -> dict[str, str]:
    return {k: html.unescape(v).strip()
            for k, v in re.findall(r'<Attribute Name="([^"]*)">([^<]*)</Attribute>', xml)}


async def _egib_point(client: httpx.AsyncClient, p: Point) -> dict[str, str]:
    """Parcel record (incl. its land-use contours) under an EPSG:2180 point."""
    x, y = p.x, p.y  # EPSG:2180 axis order in WMS 1.3.0 is northing (y), easting (x)
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo",
        "LAYERS": "kontury", "QUERY_LAYERS": "kontury", "STYLES": "", "CRS": "EPSG:2180",
        "BBOX": f"{y - 10:.2f},{x - 10:.2f},{y + 10:.2f},{x + 10:.2f}",
        "WIDTH": 21, "HEIGHT": 21, "I": 10, "J": 10,
        "INFO_FORMAT": "text/xml", "FEATURE_COUNT": 1,
    }
    r = await client.get(KIEG_URL, params=params)
    r.raise_for_status()
    return _attrs(r.text)


def _num(v: str | None) -> float | None:
    try:
        return float((v or "").replace(",", "."))
    except ValueError:
        return None


async def fetch_egib_land_use(plot_id: str, poly_2180: BaseGeometry,
                              client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Official land-use contours of the parcel (EGiB via KIEG). One point query = whole parcel."""
    inner = poly_2180.buffer(-3.0)
    pt = (inner if not inner.is_empty else poly_2180).representative_point()

    async def fetch() -> PartialResult:
        own = client is None
        c = client or httpx.AsyncClient(timeout=httpx.Timeout(9.0, connect=4.0), follow_redirects=True)
        try:
            a = await _egib_point(c, pt)
        finally:
            if own:
                await c.aclose()
        pid = a.get("Identyfikator działki")
        if not pid:
            return PartialResult({}, ["Usługa EGiB (KIEG) nie zwróciła działki w tym miejscu."])
        if pid != plot_id:
            return PartialResult({}, [f"Usługa EGiB zwróciła inną działkę ({pid}) – pomijam."])
        raw = a.get("Oznaczenie konturu") or ""
        codes = parse_egib_codes(raw) or parse_egib_codes(a.get("Oznaczenie użytku") or "")
        values = {
            "codes": codes,
            "published": bool(codes),
            "parcelAreaHa": _num(a.get("Pole pow. w ewidencji gruntów (ha)")),
            "dataDate": a.get("Data publikacji danych") or None,
        }
        # Empty contours = this starosta does not publish land use via KIEG → definitive answer.
        return PartialResult(values, [], definitive=True)

    return await run_adapter(
        KIEG_SOURCE,
        f"{KIEG_URL}?SERVICE=WMS&REQUEST=GetFeatureInfo&LAYERS=kontury",
        {"plotId": plot_id, "pt": [round(pt.x), round(pt.y)], "v": 2},
        fetch, timeout_sec=TIMEOUT_SEC, cache_ttl_sec=CACHE_TTL,
    )


# --------------------------------------------------------------------------- result


def _soil_classes(codes: list[dict[str, Any]]) -> list[str]:
    order = ["I", "II", "IIIa", "IIIb", "III", "IVa", "IVb", "IV", "V", "VI", "VIz"]
    found = {c["soilClass"] for c in codes if c.get("soilClass")}
    return sorted(found, key=lambda k: order.index(k) if k in order else 99)


def _no_data(reason: str) -> dict[str, Any]:
    return {"category": None, "labelPl": None, "isAgricultural": None, "source": None,
            "uses": [], "codes": [], "soilClasses": [], "egib": None, "notes": [reason]}


def land_use_from_egib(egib_r: dict[str, Any]) -> dict[str, Any]:
    """Adapter envelope → `landUse` dict. Only register facts; unknown stays unknown."""
    ev = egib_r.get("values") or {}
    if not ev:
        reason = "; ".join(egib_r.get("errors") or []) or "usługa nie odpowiedziała"
        return _no_data(f"Brak danych o rodzaju użytku – ewidencja gruntów (EGiB) niedostępna: {reason}.")
    codes: list[dict[str, Any]] = ev.get("codes") or []
    if not codes:
        return {**_no_data("Brak danych o rodzaju użytku – starostwo nie publikuje użytków gruntowych "
                           "w krajowej usłudze ewidencji (KIEG GUGiK)."), "egib": ev}

    cats = list(dict.fromkeys(c["category"] for c in codes))
    uses = [LABEL_PL[c] for c in cats]
    notes: list[str] = []
    if len(cats) == 1:
        category, label = cats[0], uses[0]
        is_agri: bool | None = category in AGRICULTURAL
    else:
        category, label = "mixed", f"{LABEL_PL['mixed']}: " + ", ".join(uses)
        notes.append("W ewidencji działka ma kilka użytków; ewidencja nie podaje ich powierzchni, "
                     "dlatego nie wskazujemy użytku głównego.")
        agri = [c in AGRICULTURAL for c in cats]
        is_agri = True if all(agri) else (False if not any(agri) else None)
    return {
        "category": category,
        "labelPl": label,
        "isAgricultural": is_agri,
        "source": "egib",
        "uses": uses,
        "codes": [c["code"] for c in codes],
        "soilClasses": _soil_classes(codes),
        "egib": ev,
        "notes": notes,
    }


async def classify_land_use(
    plot_id: str,
    poly_2180: BaseGeometry,
    client: httpx.AsyncClient | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """→ (landUse, sources, errors). Never raises."""
    egib_r = await fetch_egib_land_use(plot_id, poly_2180, client)
    return land_use_from_egib(egib_r), egib_r["sources"], [f"EGiB: {e}" for e in egib_r["errors"]]


__all__ = ["classify_land_use", "land_use_from_egib", "parse_egib_code", "parse_egib_codes",
           "LABEL_PL", "AGRICULTURAL"]
