"""Locate a listing (zone / quartier) and compare it to the market."""

import re
import unicodedata
from dataclasses import dataclass
from statistics import median

from . import config

# Street / landmark keywords -> quartier.
KEYWORDS = {
    "Ternes": ["ternes", "wagram", "niel", "carnot", "mac-mahon",
               "mac mahon", "pereire", "poncelet", "etoile",
               "porte maillot", "acacias"],
    "Plaine-de-Monceaux": ["monceau", "villiers", "courcelles",
                           "malesherbes", "wagram", "prony", "jouffroy",
                           "levis", "pereire"],
    "Chaillot": ["chaillot", "trocadero", "iena", "kleber", "marceau",
                 "boissiere", "victor hugo"],
    "Porte-Dauphine": ["dauphine", "foch", "pompe", "malakoff",
                       "victor hugo", "longchamp"],
    "Muette Nord": ["muette", "passy", "henri martin"],
    "Champs-Elysees": ["champs-elysees", "champs elysees", "george v",
                       "montaigne", "alma"],
    "Faubourg-du-Roule": ["roule", "friedland", "haussmann", "hoche",
                          "saint-honore", "courcelles"],
    "Madeleine": ["madeleine", "concorde", "boissy d'anglas"],
    "Europe": ["europe", "saint-lazare", "rome", "rocher", "miromesnil"],
}
EXCLUDED_17 = ["batignolles", "epinettes", "brochant", "guy moquet",
               "la fourche", "clichy-batignolles", "cardinet",
               "porte de clichy", "porte de saint-ouen"]

# Approximate border between 17e Sud (Ternes / Plaine Monceau) and the
# north (Batignolles / Epinettes): rail line + bd Pereire, as (lon, lat).
NORTH_BORDER_17 = [(2.280, 48.8810), (2.2926, 48.8857),
                   (2.3150, 48.8880), (2.3270, 48.8840)]


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    return text.encode("ascii", "ignore").decode().lower()


def _border_lat(lon):
    pts = NORTH_BORDER_17
    if lon <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= lon <= x1:
            return y0 + (y1 - y0) * (lon - x0) / (x1 - x0)
    return pts[-1][1]


def zone_from_postal_code(postal_code):
    """Return the target zone of a postal code, or None."""
    for zone, info in config.ZONES.items():
        if str(postal_code) == info["postal_code"]:
            return zone
    return None


def guess_quartier(listing, zone):
    """Guess the administrative quartier of a listing inside its zone."""
    if listing.quartier in config.ZONES[zone]["quartiers"]:
        return listing.quartier
    text = _norm(" ".join([listing.title, listing.description,
                           listing.quartier or ""]))
    for quartier in config.ZONES[zone]["quartiers"]:
        words = KEYWORDS.get(quartier, [])
        if any(re.search(r"\b" + re.escape(w) + r"\b", text)
               for w in words):
            return quartier
    return None


def is_in_17_sud(listing):
    """Tell whether a 75017 listing lies in the south (True/False)."""
    text = _norm(" ".join([listing.title, listing.description,
                           listing.quartier or ""]))
    if any(word in text for word in EXCLUDED_17):
        return False
    if listing.lat is not None and listing.lon is not None:
        return listing.lat < _border_lat(listing.lon)
    return True


def locate(listing):
    """Fill zone and quartier; return False if outside the target area."""
    zone = zone_from_postal_code(listing.postal_code)
    if zone is None:
        return False
    if zone == "17e Sud" and not is_in_17_sud(listing):
        return False
    listing.zone = zone
    listing.quartier = guess_quartier(listing, zone)
    return True


def surface_premium(surface):
    """Return the per-m2 premium factor for small flats."""
    for max_surface, factor in config.SMALL_SURFACE_PREMIUM:
        if surface < max_surface:
            return factor
    return 1.0


def reference_price_m2(zone, quartier, surface):
    """Return the expected market price per m2 for this flat."""
    base = config.MARKET_PRICE_M2.get(quartier)
    if base is None:
        base = config.ZONE_PRICE_M2[zone]
    return base * surface_premium(surface)


@dataclass
class PriceAssessment:
    """Position of a listing price against its neighbourhood."""

    price_m2: float
    reference_m2: float
    low_m2: float
    high_m2: float
    delta_pct: float
    label: str
    peers: int


def assess_price(listing, peers_m2=None, band=0.08):
    """Compare a listing price per m2 to the neighbourhood.

    The reference is the quartier average (adjusted for small surfaces),
    blended 50/50 with the median of comparable listings when at least
    five are available. The "typical" band is +/- ``band`` around it.
    """
    ref = reference_price_m2(listing.zone, listing.quartier,
                             listing.surface)
    peers = [p for p in (peers_m2 or []) if p > 0]
    if len(peers) >= 5:
        ref = 0.5 * ref + 0.5 * median(peers)
    low, high = ref * (1 - band), ref * (1 + band)
    price_m2 = listing.price_m2
    if price_m2 < low:
        label = "low"
    elif price_m2 > high:
        label = "high"
    else:
        label = "typical"
    return PriceAssessment(
        price_m2=price_m2, reference_m2=ref, low_m2=low, high_m2=high,
        delta_pct=(price_m2 / ref - 1) * 100, label=label,
        peers=len(peers))
