"""Land-use warnings: only the ones that mean something (TUZ, wrong crop on an orchard)."""

from __future__ import annotations

from app.engine.run import _crop_land_use_mismatch

ARABLE = {"category": "arable", "labelPl": "grunt orny (pole uprawne)", "isAgricultural": True}
ORCHARD = {"category": "orchard", "labelPl": "sad", "isAgricultural": True}
MEADOW = {"category": "meadow", "labelPl": "łąka", "isAgricultural": True}


def test_no_warning_for_plantations_on_arable_land() -> None:
    # raspberries / strawberries / fruit trees very often stay "grunt orny" in EGiB
    for crop in ("krzewy", "truskawki", "drzewa"):
        assert _crop_land_use_mismatch(crop, crop, ARABLE) is None


def test_wrong_crop_on_orchard_still_warns() -> None:
    assert "sad" in (_crop_land_use_mismatch("zboza_ozime", "Zboża ozime", ORCHARD) or "")


def test_grassland_still_warns_about_tuz() -> None:
    assert "TUZ" in (_crop_land_use_mismatch("zboza_ozime", "Zboża ozime", MEADOW) or "")
