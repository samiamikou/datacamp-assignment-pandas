"""Client for Figaro Immobilier search pages (immobilier.lefigaro.fr).

The public result pages embed their data (Nuxt payload); filters are
query parameters. Pages are fetched slowly, with an honest user agent.
"""

import time

import requests

from .. import config, market
from ..listing import Listing
from . import nuxt_payload
from .bienici import SourceError, classify, _period

BASE = ("https://immobilier.lefigaro.fr/annonces/"
        "immobilier-vente-appartement-{slug}.html")
SLUGS = {"75008": "paris+8eme+75008", "75116": "paris+16eme+75116",
         "75017": "paris+17eme+75017"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; apartment-analyzer/0.2)",
           "Accept-Language": "fr-FR,fr;q=0.9"}
PAUSE_S = 1.0


def _page(slug, params, timeout=25):
    try:
        resp = requests.get(BASE.format(slug=slug), params=params,
                            headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        data = nuxt_payload.load(resp.text)
        return data["data"]["classifiedsListResponse"]
    except (requests.RequestException, ValueError, KeyError,
            TypeError) as exc:
        raise SourceError(f"Figaro Immobilier request failed: {exc}") \
            from exc


def _surface(ad):
    surface = float(ad.get("area") or 0)
    carrez = market.carrez_surface(ad.get("description"))
    return carrez if carrez and 9 <= carrez < surface else surface


def _elevator(ad, text):
    if "ascenseur" in (ad.get("options") or []):
        return True
    return market.elevator_from_text(text)


def _to_listing(ad, postal_code):
    loc = ad.get("location") or {}
    place = classify(loc.get("district"), postal_code, loc.get("latitude"))
    if place is None or not ad.get("area") or not ad.get("price"):
        return None
    if not loc.get("district") and postal_code == "75017":
        place = (None, None)  # let market.locate use the map position
    text = ad.get("description") or ""
    rooms = ad.get("roomCount") or [1]
    zone, quartier = place
    return Listing(
        title=" - ".join(x for x in (ad.get("roomCountLabel") or "Appartement",
                                     loc.get("district")) if x),
        price=float(ad["price"]), surface=_surface(ad),
        postal_code=config.ZONES[zone]["postal_code"] if zone else postal_code,
        rooms=int(min(rooms) if isinstance(rooms, list) else rooms),
        zone=zone, quartier=quartier, district=loc.get("district"),
        dpe=((ad.get("dpe") or {}).get("energyCategory") or None),
        floor=market.floor_from_text(text), elevator=_elevator(ad, text),
        construction_period=_period(market.year_from_text(text)),
        url=ad.get("recordLink") or "", source="figaro",
        lat=loc.get("latitude"), lon=loc.get("longitude"),
        description=text,
        price_decreased=bool(ad.get("priceDownPercentage")))


def search(postal_code, min_price, max_price, min_surface, max_pages=5):
    """Return Figaro Immobilier listings matching the criteria."""
    slug = SLUGS.get(postal_code)
    if slug is None:
        raise SourceError(f"No Figaro Immobilier page for {postal_code}")
    params = {"priceMin": int(min_price), "priceMax": int(max_price),
              "areaMin": int(min_surface)}
    listings = []
    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(PAUSE_S)
            params["page"] = page
        resp = _page(slug, params)
        for ad in resp.get("classifieds") or []:
            item = _to_listing(ad, postal_code)
            if item is not None:
                listings.append(item)
        if page >= (resp.get("pagination") or {}).get("totalPage", 1):
            break
    return listings
