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
                       "longitude": 2.29, "postalCode": "75017"},
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


def test_same_ad_posted_in_two_zones_is_merged():
    """Check one agency ad listed under two zones is kept once."""
    text = "Studio lumineux au 3e étage, proche du parc Monceau, " * 3
    a = Listing(title="Appartement", price=240000, surface=19,
                postal_code="75008", zone="8e", source="bienici",
                url="https://bienici/a", description=text)
    b = Listing(title="Appartement", price=240000, surface=19,
                postal_code="75017", zone="17e Sud", source="bienici",
                url="https://bienici/b", description=text)
    assert len(filter_listings([a, b])) == 1


def test_ground_floor_flats_are_excluded():
    """Check rez-de-chaussee flats are dropped, from the field or text."""
    base = dict(title="Studio", price=220000, surface=21, postal_code="75017",
                zone="17e Sud", quartier="Ternes")
    kept = filter_listings([
        Listing(floor=0, url="a", **base),
        Listing(description="Studio en rez-de-chaussée sur cour", url="b",
                **{**base, "price": 221000}),
        Listing(floor=3, url="c", **{**base, "price": 222000})])
    assert [x.url for x in kept] == ["c"]


def test_15e_nord_districts():
    """Check the 15e is split into north (kept) and south (excluded)."""
    assert classify("Dupleix - Motte Picquet", "75015") == (
        "15e Nord", "Grenelle")
    assert classify("Cambronne-Garibaldi", "75015") == ("15e Nord", "Necker")
    assert classify("Vaugirard - Parc des Expositions", "75015") is None
    assert classify("Citroën-Boucicaut", "75015") is None
    assert classify("Grenelle-Javel", "75015", lat=48.850) == (
        "15e Nord", "Grenelle")
    assert classify("Grenelle-Javel", "75015", lat=48.838) is None
    assert classify(None, "75015", lat=48.836) is None
    flat = Listing(title="Studio", price=220000, surface=20,
                   postal_code="75015", description="métro Cambronne")
    assert market.locate(flat) and flat.quartier == "Necker"
    south = Listing(title="Studio", price=220000, surface=20,
                    postal_code="75015", description="Porte de Versailles")
    assert not market.locate(south)


def test_figaro_ads_outside_the_arrondissement_are_dropped():
    """Check an ad from outside Paris is rejected for a 16e search."""
    ad = {"area": 40, "price": 230000, "roomCount": [2], "description": "",
          "location": {"district": None, "latitude": 48.90,
                       "longitude": 2.40, "postalCode": "93500"}}
    assert figaro._to_listing(ad, "75116") is None
    ad["location"].update(postalCode="75016", latitude=48.865,
                          longitude=2.28)
    assert figaro._to_listing(ad, "75116").zone == "16e Nord"


def test_paruvendu_card_parsing():
    """Check a ParuVendu result card becomes a located listing."""
    from apartment_analyzer.sources import paruvendu
    card = (' data-id="1" ><a href="/immobilier/vente/appartement/1A1KIV" '
            'title=" Appartement - 1 pièce(s) - 21 m²"><img src="https://img.'
            'paruvendu.fr/media_ext/x.jpg"></a><span>236 250 €</span>'
            '<p>DPE :</p><b>F</b><p>Studio rue du Commerce au 4ème étage avec '
            'ascenseur, parfait état, proche métro Commerce et Émile Zola.</p>')
    item = paruvendu.parse_card(card, "75015")
    assert item.price == 236250 and item.surface == 21 and item.dpe == "F"
    assert item.floor == 4 and item.elevator is True
    assert item.url.startswith("https://www.paruvendu.fr/immobilier/vente/")
    assert market.locate_by_text(item) and item.zone == "15e Nord"


def test_text_only_listings_need_a_landmark_in_split_zones():
    """Check a 16e ad with no northern landmark is not kept."""
    vague = Listing(title="Studio", price=230000, surface=20,
                    postal_code="75016", description="Beau studio lumineux")
    assert not market.locate_by_text(vague)
    north = Listing(title="Studio", price=230000, surface=20,
                    postal_code="75016", description="Proche Trocadéro")
    assert market.locate_by_text(north) and north.quartier == "Chaillot"


def test_notaires_ad_to_listing():
    """Check a notarial sale is parsed and auctions are skipped."""
    from apartment_analyzer.sources import notaires
    ad = {"typeTransaction": "VENTE", "viager": "NON", "prixTotal": 242000,
          "surface": 27.88, "codePostal": "75008", "nbPieces": 1,
          "descriptionFr": "PARIS 08 / SAINT AUGUSTIN - Studio 3e étage",
          "urlDetailAnnonceFr": "https://www.immobilier.notaires.fr/fr/x"}
    item = notaires._to_listing(ad)
    assert item.zone == "8e" and item.price == 242000 and item.floor == 3
    assert notaires._to_listing({**ad, "typeTransaction": "VNI"}) is None


def test_implausibly_cheap_ads_are_dropped():
    """Check an ad far below Paris prices (misfiled) is filtered out."""
    cheap = Listing(title="F3", price=245000, surface=66, postal_code="75017",
                    zone="17e Sud", quartier="Ternes", url="x")
    assert filter_listings([cheap]) == []
