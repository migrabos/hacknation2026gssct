"""Crop profiles for "which crop copes best with the water on this plot" (engine/crop_fit.py).

Finer than the IUNG groups in catalog.py on purpose: inside one group the answer differs
(rye grows on sand, wheat does not; lupin vs pea; strawberries vs raspberries). Every profile
points back to its catalog group (`group`), so the farmer can re-run /analyze for that crop.

Values are orientation values, not variety-level agronomy. Sources follow the bibliography of the
KOWR challenge material "Podstawy naukowe oceny sytuacji wodnej…" (HackNation 2026):
* rootDepthM – typical maximum rooting depth from the FAO-56 rooting-depth table (Allen, Pereira,
  Raes & Smith 1998, Table 22; the KOWR material cites FAO-56 Rev. 1, 2025), mid of the range.
  Lupin is not in the table: estimated from its deep taproot.
* sensitivity – drought sensitivity 0–1, ordered after FAO-33 yield response factors (Ky) and kept
  consistent with the IUNG-PIB crop groups of the System Monitoringu Suszy Rolniczej
  (Doroszewski et al. 2012) used in catalog.py. The 0–1 scale itself is ours.
* soilNeed – how good a soil the crop needs: "low" = copes on light, poor soils (rye complexes),
  "high" = needs good soils (wheat complexes). Expert classification after the Polish soil
  valuation / IUNG agricultural suitability complexes — NOT taken from an IUNG table.
* wetTolerance – tolerance of standing water / waterlogging (expert classification).
* erosionRisk – soil left bare between rows / for long periods on a slope ("high" = row crops).
The KOWR material gives no crop-level numbers; it requires that crop water needs and sensitivity
are considered and that uncertainty is shown — see `NOT_CONSIDERED` / `UNCERTAINTY` in crop_fit.py.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Level = Literal["low", "medium", "high"]


class FitProfile(TypedDict):
    id: str
    namePl: str
    group: str  # catalog.py crop id
    rootDepthM: float
    sensitivity: float
    soilNeed: Level
    wetTolerance: Level
    erosionRisk: Level


_P = FitProfile

FIT_PROFILES: tuple[FitProfile, ...] = (
    _P(id="pszenica_ozima", namePl="Pszenica ozima", group="zboza_ozime",
       rootDepthM=1.6, sensitivity=0.50, soilNeed="high", wetTolerance="medium", erosionRisk="low"),
    _P(id="zyto", namePl="Żyto", group="zboza_ozime",
       rootDepthM=1.2, sensitivity=0.35, soilNeed="low", wetTolerance="medium", erosionRisk="low"),
    _P(id="pszenzyto", namePl="Pszenżyto ozime", group="zboza_ozime",
       rootDepthM=1.2, sensitivity=0.40, soilNeed="medium", wetTolerance="medium", erosionRisk="low"),
    _P(id="jeczmien_jary", namePl="Jęczmień jary", group="zboza_jare",
       rootDepthM=1.2, sensitivity=0.60, soilNeed="high", wetTolerance="low", erosionRisk="medium"),
    _P(id="owies", namePl="Owies", group="zboza_jare",
       rootDepthM=1.2, sensitivity=0.65, soilNeed="low", wetTolerance="medium", erosionRisk="medium"),
    _P(id="kukurydza", namePl="Kukurydza", group="kukurydza",
       rootDepthM=1.3, sensitivity=0.75, soilNeed="medium", wetTolerance="low", erosionRisk="high"),
    _P(id="rzepak", namePl="Rzepak ozimy", group="rzepak",
       rootDepthM=1.2, sensitivity=0.55, soilNeed="high", wetTolerance="low", erosionRisk="low"),
    _P(id="burak", namePl="Burak cukrowy", group="burak",
       rootDepthM=0.9, sensitivity=0.60, soilNeed="high", wetTolerance="low", erosionRisk="high"),
    _P(id="ziemniak", namePl="Ziemniak", group="ziemniak",
       rootDepthM=0.5, sensitivity=0.75, soilNeed="low", wetTolerance="low", erosionRisk="high"),
    _P(id="groch_bobik_soja", namePl="Groch, bobik, soja", group="straczkowe",
       rootDepthM=0.8, sensitivity=0.60, soilNeed="medium", wetTolerance="medium", erosionRisk="medium"),
    _P(id="lubin", namePl="Łubin", group="straczkowe",
       rootDepthM=1.0, sensitivity=0.50, soilNeed="low", wetTolerance="low", erosionRisk="medium"),
    _P(id="lucerna", namePl="Lucerna", group="uzytki_zielone",
       rootDepthM=1.5, sensitivity=0.30, soilNeed="high", wetTolerance="low", erosionRisk="low"),
    _P(id="laka", namePl="Łąka / pastwisko (trawy, koniczyna)", group="uzytki_zielone",
       rootDepthM=0.8, sensitivity=0.55, soilNeed="medium", wetTolerance="high", erosionRisk="low"),
    _P(id="warzywa", namePl="Warzywa gruntowe", group="warzywa",
       rootDepthM=0.45, sensitivity=0.85, soilNeed="high", wetTolerance="low", erosionRisk="high"),
    _P(id="sad", namePl="Sad (jabłonie, wiśnie, śliwy)", group="sad",
       rootDepthM=1.5, sensitivity=0.80, soilNeed="medium", wetTolerance="low", erosionRisk="low"),
    _P(id="truskawki", namePl="Truskawki", group="jagodowe",
       rootDepthM=0.25, sensitivity=0.90, soilNeed="medium", wetTolerance="low", erosionRisk="medium"),
    _P(id="krzewy_jagodowe", namePl="Malina, porzeczka, agrest", group="jagodowe",
       rootDepthM=0.9, sensitivity=0.75, soilNeed="medium", wetTolerance="low", erosionRisk="low"),
)
