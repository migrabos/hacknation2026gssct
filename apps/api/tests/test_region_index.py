"""Offline obręb search (plot/region_index.py) — real PRG index, no network."""

from __future__ import annotations

import pytest

from plot.region_index import load_index, norm, search

pytestmark = pytest.mark.skipif(not load_index(), reason="plot/data/regions_pl.json.gz not built")


def ids(results: list[dict]) -> set[str]:
    return {r["regionId"] for r in results}


def test_norm() -> None:
    assert norm("Zdziłowice-Kolonia") == "zdzilowice kolonia"
    assert norm("  ŁÓDŹ ") == "lodz"


def test_village_split_into_several_obreby() -> None:
    # "Zdziłowice" is not an obręb name — only "Zdziłowice Pierwsze/Drugie/Czwarte…" are.
    res, _ = search("Zdziłowice")
    assert {"060504_2.0011", "060504_2.0012", "060504_2.0013"} <= ids(res)


def test_no_diacritics_and_prefix() -> None:
    assert "060504_2.0013" in ids(search("zdzilowice pierw")[0])


def test_search_by_gmina_lists_its_obreby() -> None:
    res, total = search("Godziszów")
    assert "060504_2.0007" in ids(res)  # Piłatka, gmina Godziszów
    assert total >= 10


def test_comma_filter_narrows() -> None:
    res, _ = search("Zdziłowice, janowski")
    assert res and all(r["county"] and "janowski" in r["county"] for r in res)


def test_result_shape_matches_web_region() -> None:
    r = search("Zdziłowice Pierwsze")[0][0]
    assert set(r) == {"regionId", "region", "commune", "county", "voivodeship", "bbox"}
    assert r["region"] == "Zdziłowice Pierwsze" and r["commune"] == "Godziszów"
    assert r["voivodeship"] == "lubelskie"
