"""Client for immobilier.notaires.fr, the notaries' property listings.

Uses the public JSON service behind the search pages. The site asks
robots for 10 seconds between requests (robots.txt), which is respected.
Only classic sales are kept: notarial auctions (VNI / VAE) show a
starting price, not a sale price.
"""

import time

import requests

from .. import market
from ..listing import Listing
from .bienici import SourceError

API = ("https://www.immobilier.notaires.fr/pub-services/"
       "inotr-www-annonces/v1/annonces")
LOCALITES = {"75008": ["32464"], "75116": ["32472", "32473"],
             "75017": ["32474"], "75015": ["32471"]}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; apartment-analyzer/0.3)"}
CRAWL_DELAY_S = 10
_last_call = [0.0]


def _get(params, timeout=25):
    wait = CRAWL_DELAY_S - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()
    try:
        resp = requests.get(API, params=params, headers=HEADERS,
                            timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceError(f"Notaires request failed: {exc}") from exc


def _to_listing(ad):
    if ad.get("viager") == "OUI" or ad.get("typeTransaction") != "VENTE":
        return None
    text = ad.get("descriptionFr") or ""
    photo = ad.get("urlPhotoPrincipale")
    item = Listing(
        title=text.split(" - ")[0][:80] or "Appartement (notaire)",
        price=float(ad.get("prixTotal") or ad.get("prixAffiche") or 0),
        surface=float(ad.get("surface") or 0),
        postal_code=str(ad.get("codePostal") or ""),
        rooms=int(ad.get("nbPieces") or 1),
        floor=market.floor_from_text(text),
        elevator=market.elevator_from_text(text),
        url=ad.get("urlDetailAnnonceFr") or "", source="notaires",
        description=text, photos=[photo] if photo else [])
    return item if market.locate_by_text(item) else None


def search(postal_code, min_price, max_price, min_surface, max_pages=3):
    """Return notarial sales in a postal code matching the criteria."""
    listings = []
    for localite in LOCALITES.get(postal_code, []):
        for page in range(1, max_pages + 1):
            data = _get({"page": page, "parPage": 100, "typeBiens": "APP",
                         "typeTransactions": "VENTE",
                         "localites": localite})
            for ad in data.get("annonceResumeDto") or []:
                if not (min_price <= (ad.get("prixTotal") or 0) <= max_price
                        and (ad.get("surface") or 0) >= min_surface):
                    continue
                item = _to_listing(ad)
                if item is not None:
                    listings.append(item)
            if page >= (data.get("nbPages") or 1):
                break
    return listings
