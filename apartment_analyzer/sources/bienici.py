"""Best-effort client for the public Bien'ici search JSON endpoint.

Bien'ici aggregates most Paris agency listings (SeLoger, agencies...).
The endpoint is undocumented and may change or rate-limit: errors are
raised as ``SourceError`` so callers can fall back to CSV / manual input.
"""

import json
import re
import unicodedata

import requests

from .. import config
from ..listing import Listing
from ..market import carrez_surface

SEARCH_URL = "https://www.bienici.com/realEstateAds.json"
SUGGEST_URL = "https://res.bienici.com/suggest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (apartment-analyzer)",
           "Accept": "application/json"}
PERIODS = [(1946, "avant 1946"), (1971, "1946-1970"),
           (1991, "1971-1990")]


# Bien'ici district names -> (zone, quartier); None = outside target area.
DISTRICTS = {
    "mairie": ("8e", "Europe"),
    "europe": ("8e", "Europe"),
    "elysee - madeleine": ("8e", "Madeleine"),
    "madeleine": ("8e", "Madeleine"),
    "hoche friedland": ("8e", "Faubourg-du-Roule"),
    "saint-philippe du roule": ("8e", "Faubourg-du-Roule"),
    "saint philippe du roule": ("8e", "Faubourg-du-Roule"),
    "elysees-madeleine": ("8e", "Madeleine"),
    "parc monceau": ("8e", "Europe"),
    "porte dauphine": ("16e Nord", "Porte-Dauphine"),
    "pereire-malesherbes": ("17e Sud", "Plaine-de-Monceaux"),
    "champs-elysees": ("8e", "Champs-Elysees"),
    "chaillot": ("16e Nord", "Chaillot"),
    "dauphine": ("16e Nord", "Porte-Dauphine"),
    "muette-nord - trocadero": ("16e Nord", "Muette Nord"),
    "ternes - maillot": ("17e Sud", "Ternes"),
    "pereire": ("17e Sud", "Ternes"),
    "champerret - berthier": ("17e Sud", "Ternes"),
    "courcelles - wagram": ("17e Sud", "Plaine-de-Monceaux"),
    "legendre - levis": ("17e Sud", "Plaine-de-Monceaux"),
}
EXCLUDED = ["auteuil", "saint-cloud", "muette-sud", "maison de la radio",
            "passy", "bois de boulogne",
            "batignolles", "fourche", "epinettes", "porte de clichy"]
ZONE_OF_SEARCH = {"75008": "8e", "75116": "16e Nord", "75017": "17e Sud"}
NORTH_16_MIN_LAT = 48.8600


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"\s*-\s*", "-", text)


_DISTRICT_KEYS = {_norm(k): v for k, v in DISTRICTS.items()}


def classify(district_name, search_postal_code, lat=None):
    """Return (zone, quartier) for a portal district name, or None if out.

    Works for Bien'ici and Figaro Immobilier district labels.
    """
    name = _norm(district_name)
    if name in _DISTRICT_KEYS:
        return _DISTRICT_KEYS[name]
    if any(word in name for word in EXCLUDED):
        return None
    zone = ZONE_OF_SEARCH.get(search_postal_code)
    if zone == "16e Nord" and (lat is None or lat < NORTH_16_MIN_LAT):
        return None
    return (zone, None) if zone else None


class SourceError(RuntimeError):
    """Raised when the remote source cannot be queried."""


def _get(url, params, timeout=20):
    try:
        resp = requests.get(url, params=params, headers=HEADERS,
                            timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceError(f"Bien'ici request failed: {exc}") from exc


def zone_ids(postal_code):
    """Return Bien'ici zone ids for a postal code."""
    items = _get(SUGGEST_URL, {"q": postal_code})
    for item in items:
        if postal_code in (item.get("postalCodes") or []):
            return item.get("zoneIds") or []
    if items:
        return items[0].get("zoneIds") or []
    raise SourceError(f"No Bien'ici zone for {postal_code}")


def _period(year):
    if not year:
        return "avant 1946"
    for limit, label in PERIODS:
        if year < limit:
            return label
    return "apres 1990"


def _to_listing(ad, search_postal_code):
    pos = (ad.get("blurInfo") or {}).get("position") or {}
    district = ad.get("district") or {}
    place = classify(district.get("libelle"), search_postal_code,
                     pos.get("lat"))
    if place is None:
        return None
    zone, quartier = place
    photos = [p.get("url") for p in ad.get("photos") or [] if p.get("url")]
    surface = float(ad.get("surfaceArea") or 0)
    carrez = carrez_surface(ad.get("description"))
    if carrez and 9 <= carrez < surface:
        surface = carrez  # legal (Carrez) surface drives price and rent
    return Listing(
        title=ad.get("title") or f"{ad.get('roomsQuantity', '?')} pieces",
        price=float(ad.get("price") or 0),
        surface=surface,
        postal_code=config.ZONES[zone]["postal_code"],
        rooms=int(ad.get("roomsQuantity") or 1),
        zone=zone, quartier=quartier,
        district=district.get("libelle"),
        annual_condo_fees=ad.get("annualCondominiumFees"),
        price_decreased=bool(ad.get("priceHasDecreased")),
        dpe=ad.get("energyClassification"),
        floor=ad.get("floor"),
        elevator=ad.get("hasElevator"),
        construction_period=_period(ad.get("yearOfConstruction")),
        url=f"https://www.bienici.com/annonce/{ad.get('id')}",
        source="bienici",
        lat=pos.get("lat"), lon=pos.get("lon"),
        description=ad.get("description") or "",
        photos=photos[:5])


def search(postal_code, min_price, max_price, min_surface, max_pages=5):
    """Return listings for sale in a postal code matching the criteria."""
    ids = zone_ids(postal_code)
    listings, page_size = [], 24
    for page in range(max_pages):
        filters = {
            "size": page_size, "from": page * page_size,
            "filterType": "buy", "propertyType": ["flat"],
            "minPrice": min_price, "maxPrice": max_price,
            "minArea": min_surface, "onTheMarket": [True],
            "sortBy": "publicationDate", "sortOrder": "desc",
            "zoneIdsByTypes": {"zoneIds": ids},
        }
        data = _get(SEARCH_URL, {"filters": json.dumps(filters)})
        ads = data.get("realEstateAds") or []
        found = (_to_listing(ad, postal_code) for ad in ads)
        listings += [x for x in found if x is not None]
        if len(ads) < page_size:
            break
    return listings
