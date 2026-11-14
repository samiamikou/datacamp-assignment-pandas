"""Tests for portal parsing (no network)."""

import json

from apartment_analyzer import market
from apartment_analyzer.agent import filter_listings
from apartment_analyzer.listing import Listing
from apartment_analyzer.sources import figaro, nuxt_payload
from apartment_analyzer.sources.bienici import classify


def _page(payload):
    return ('<script type="application/json" id="__NUXT_DATA__">'
            + json.dumps(payload) + "</script>")


def test_nuxt_payload_decoding():
    """Check index references and wrappers are resolved."""
    raw = [["ShallowReactive", 1], {"data": 2}, {"items": 3}, [4],
           {"price": 5, "tags": 6}, 210000, ["Reactive", 7], [8], "a"]
    data = nuxt_payload.load(_page(raw))
    assert data["data"]["items"][0]["price"] == 210000
    assert data["data"]["items"][0]["tags"] == ["a"]
    assert nuxt_payload.load("<html></html>") is None


def test_figaro_ad_to_listing():
    """Check a Figaro ad becomes a located listing."""
    ad = {"area": 21, "price": 230000, "roomCount": [1],
          "roomCountLabel": "1 pièce",
          "description": "Studio au 3e étage avec ascenseur, 19,5 m2 "
                         "Carrez, immeuble de 1930.",
          "dpe": {"energyCategory": "D"}, "options": [],
          "location": {"district": "Ternes-Maillot", "latitude": 48.88,
                       "longitude": 2.29},
          "recordLink": "https://immobilier.lefigaro.fr/annonces/x.html"}
    item = figaro._to_listing(ad, "75017")
    assert (item.zone, item.quartier) == ("17e Sud", "Ternes")
    assert item.surface == 19.5 and item.floor == 3 and item.elevator
    assert item.dpe == "D" and item.construction_period == "avant 1946"
    ad["location"]["district"] = "Batignolles-Cardinet"
    assert figaro._to_listing(ad, "75017") is None


def test_district_names_from_both_portals():
    """Check Bien'ici and Figaro spellings map to the same quartier."""
    assert classify("Legendre - Lévis", "75017") == classify(
        "Legendre-Lévis", "75017")
    assert classify("Elysées-Madeleine", "75008")[1] == "Madeleine"
    assert classify("Auteuil Sud", "75116") is None


def test_text_helpers():
    """Check floor / lift / year parsing from ad text."""
    assert market.floor_from_text("au 6ème et dernier étage") == 6
    assert market.floor_from_text("en rez-de-chaussée sur cour") == 0
    assert market.elevator_from_text("5e étage sans ascenseur") is False
    assert market.year_from_text("immeuble ancien de 1880") == 1880


def test_duplicates_across_portals_are_merged():
    """Check the same flat from two portals is kept once."""
    a = Listing(title="Studio", price=220000, surface=21.5,
                postal_code="75017", zone="17e Sud", quartier="Ternes",
                source="bienici", url="https://bienici/1")
    b = Listing(title="1 pièce", price=220000, surface=21.5,
                postal_code="75017", zone="17e Sud", quartier="Ternes",
                source="figaro", url="https://figaro/1", dpe="F")
    kept = filter_listings([a, b])
    assert len(kept) == 1
    assert kept[0].source == "bienici+figaro" and kept[0].dpe == "F"
    assert kept[0].other_urls == ["https://figaro/1"]
