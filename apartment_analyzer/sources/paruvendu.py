"""Client for ParuVendu search pages (agencies and private sellers).

Result pages are plain HTML cards; price and surface filters are query
parameters. Ad detail pages are not fetched (robots.txt disallows them).
"""

import html
import re
import time

import requests

from .. import market
from ..listing import Listing
from .bienici import SourceError

BASE = "https://www.paruvendu.fr/immobilier/vente/appartement/paris-{cp}/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; apartment-analyzer/0.3)",
           "Accept-Language": "fr-FR,fr;q=0.9"}
PAUSE_S = 2.0
SITE = "https://www.paruvendu.fr"
SEARCH_CODES = {"75008": ["75008"], "75116": ["75016"],
                "75017": ["75017"], "75015": ["75015"]}

PRICE_RE = re.compile(r"(\d{1,3}(?:[\s  ]\d{3})+|\d{4,})\s*€")
SURFACE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m²")
ROOMS_RE = re.compile(r"(\d+)\s*pi[eè]ce")
DPE_RE = re.compile(r"DPE\s*:\s*\|\s*([A-G])\b")
LINK_RE = re.compile(r'href="(/immobilier/vente/[a-z-]+/\d+[A-Z0-9]*)"')
TITLE_RE = re.compile(r'<a href="/immobilier/vente/[^"]+" title="([^"]+)"')
IMG_RE = re.compile(r"https://img\.paruvendu\.fr/media_ext/[^\"'\s]+")


def _text(block):
    block = re.sub(r"<(script|style)\b.*?</\1>", " ", block, flags=re.S)
    block = re.sub(r"<[^>]+>", "|", block)
    return html.unescape(re.sub(r"\s*\|[\s|]*", " | ", block))


def _number(raw):
    return float(re.sub(r"[\s  ]", "", raw).replace(",", "."))


def parse_card(block, postal_code):
    """Return a Listing from one result card, or None."""
    link = LINK_RE.search(block)
    title = TITLE_RE.search(block)
    text = _text(block)
    price = PRICE_RE.search(text)
    surface = SURFACE_RE.search(html.unescape(title.group(1))) \
        if title else None
    if not (link and price and surface):
        return None
    parts = [p.strip() for p in text.split("|")]
    desc = max(parts, key=len) if parts else ""
    dpe = DPE_RE.search(text)
    rooms = ROOMS_RE.search(text)
    item = Listing(
        title=html.unescape(title.group(1)).strip(" -"),
        price=_number(price.group(1)), surface=_number(surface.group(1)),
        postal_code=postal_code, rooms=int(rooms.group(1)) if rooms else 1,
        dpe=dpe.group(1) if dpe else None,
        floor=market.floor_from_text(desc),
        elevator=market.elevator_from_text(desc),
        url=SITE + link.group(1), source="paruvendu", description=desc,
        photos=list(dict.fromkeys(IMG_RE.findall(block)))[:5])
    carrez = market.carrez_surface(desc)
    if carrez and 9 <= carrez < item.surface:
        item.surface = carrez
    return item


def _page(code, params, timeout=25):
    try:
        resp = requests.get(BASE.format(cp=code), params=params,
                            headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        raise SourceError(f"ParuVendu request failed: {exc}") from exc


def search(postal_code, min_price, max_price, min_surface, max_pages=4):
    """Return ParuVendu listings in a postal code matching the criteria."""
    listings = []
    for code in SEARCH_CODES.get(postal_code, []):
        for page in range(1, max_pages + 1):
            params = {"px0": int(min_price), "px1": int(max_price),
                      "sur0": int(min_surface)}
            if page > 1:
                params["p"] = page
            time.sleep(PAUSE_S)
            blocks = _page(code, params).split('class="blocAnnonce')[1:]
            for block in blocks:
                item = parse_card(block, code)
                if item is not None and market.locate_by_text(item):
                    listings.append(item)
            if len(blocks) < 30:
                break
    return listings
