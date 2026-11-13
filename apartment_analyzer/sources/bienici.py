"""Best-effort client for the public Bien'ici search JSON endpoint.

Bien'ici aggregates most Paris agency listings (SeLoger, agencies...).
The endpoint is undocumented and may change or rate-limit: errors are
raised as ``SourceError`` so callers can fall back to CSV / manual input.
"""

import json

import requests

from ..listing import Listing

SEARCH_URL = "https://www.bienici.com/realEstateAds.json"
SUGGEST_URL = "https://res.bienici.com/suggest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (apartment-analyzer)",
           "Accept": "application/json"}
PERIODS = [(1946, "avant 1946"), (1971, "1946-1970"),
           (1991, "1971-1990")]


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


def _to_listing(ad):
    pos = (ad.get("blurInfo") or {}).get("position") or {}
    district = ad.get("district") or {}
    photos = [p.get("url") for p in ad.get("photos") or [] if p.get("url")]
    return Listing(
        title=ad.get("title") or f"{ad.get('roomsQuantity', '?')} pieces",
        price=float(ad.get("price") or 0),
        surface=float(ad.get("surfaceArea") or 0),
        postal_code=str(ad.get("postalCode") or ""),
        rooms=int(ad.get("roomsQuantity") or 1),
        quartier=district.get("libelle") or district.get("name"),
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
        listings += [_to_listing(ad) for ad in ads]
        if len(ads) < page_size:
            break
    return listings
