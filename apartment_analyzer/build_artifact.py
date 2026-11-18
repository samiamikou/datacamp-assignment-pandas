r"""Build the "Paris Studio Investor" artifact from a fresh live search.

Usage::

    python -m apartment_analyzer.build_artifact --out build/ \\
        [--previous previous_data.json]

Writes ``index.html`` (the page, data inline), ``data.json`` (today's
snapshot, read back tomorrow for "new" badges), ``photos/*.jpg`` and
``files.json``: the ``files`` map to publish, with ``null`` for photos of
the previous snapshot that are no longer used.
"""

import argparse
import datetime as dt
import hashlib
import io
import json
import re
from pathlib import Path

import requests

from . import config
from .agent import LAST_ERRORS, fetch, filter_listings

TEMPLATE = Path(__file__).resolve().parent / "artifact" / "template.html"
PHOTOS_PER_LISTING = 4
PHOTO_WIDTH = 720
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; apartment-analyzer/0.3)"}


def listing_key(listing):
    """Return a stable key for a flat across days."""
    base = listing.url or f"{listing.title}{listing.price}{listing.surface}"
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\+?\d[\d .]{8,}\d", "[tel]", text)  # no phone numbers
    return re.sub(r"\s+", " ", text).strip()[:520]


PORTALS = {"lefigaro": "Figaro Immobilier", "paruvendu": "ParuVendu",
           "notaires": "Notaires de France", "bienici": "Bien'ici"}


def _portal(url):
    return next((name for key, name in PORTALS.items() if key in url),
                "Bien'ici")


def download_photo(url, dest):
    """Download, shrink and save one photo as JPEG; return True on success."""
    from PIL import Image
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    except (requests.RequestException, OSError):
        return False
    if img.width > PHOTO_WIDTH:
        img = img.resize((PHOTO_WIDTH,
                          round(img.height * PHOTO_WIDTH / img.width)))
    img.save(dest, "JPEG", quality=72, optimize=True)
    return True


def _photos(listing, key, out_dir):
    paths = []
    for i, url in enumerate(listing.photos[:PHOTOS_PER_LISTING], 1):
        rel = f"photos/{key}-{i}.jpg"
        if download_photo(url, out_dir / rel):
            paths.append(rel)
    return paths


def _row(lid, listing, key, photos, first_seen):
    urls = [listing.url] + listing.other_urls
    return {
        "id": lid, "key": key, "title": listing.title.strip(),
        "url": listing.url,
        "links": [{"portal": _portal(u), "url": u} for u in urls if u],
        "zone": listing.zone, "quartier": listing.quartier,
        "district": listing.district, "price": listing.price,
        "surface": listing.surface, "rooms": listing.rooms,
        "dpe": listing.dpe if listing.dpe in list("ABCDEFG") else None,
        "floor": listing.floor, "elevator": listing.elevator,
        "period": listing.construction_period,
        "condo": listing.annual_condo_fees,
        "reduced": listing.price_decreased, "desc": _clean(
            listing.description), "photos": photos, "first_seen": first_seen,
    }


def _config():
    return {
        "market": config.MARKET_PRICE_M2, "zonePrice": config.ZONE_PRICE_M2,
        "premium": config.SMALL_SURFACE_PREMIUM,
        "rentBase": config.RENT_CAP_M2_BASE,
        "zoneRent": config.ZONE_RENT_CAP_M2,
        "furnished": config.FURNISHED_FACTOR,
        "rooms": {str(k): v for k, v in config.ROOMS_FACTOR.items()},
        "period": config.PERIOD_FACTOR, "tf": config.TAXE_FONCIERE_M2,
        "copro": config.COPRO_CHARGES_M2,
        "nonrec": config.NON_RECOVERABLE_SHARE,
        "dpe": {k: list(v) for k, v in config.DPE_RULES.items()},
    }


def build(out_dir, previous=None, today=None, tolerance=0.05):
    """Run the search and write the artifact files; return a summary."""
    today = today or dt.date.today().isoformat()
    out_dir = Path(out_dir)
    (out_dir / "photos").mkdir(parents=True, exist_ok=True)
    crit = dict(config.SEARCH)
    raw = fetch("all", criteria={
        "min_price": crit["min_price"] * (1 - tolerance),
        "max_price": crit["max_price"] * (1 + tolerance),
        "min_surface": crit["min_surface"]})
    listings = filter_listings(raw, crit, tolerance)
    seen = {}
    for old in (previous or {}).get("listings", []):
        old_key = old.get("key") or (hashlib.sha1(
            old["url"].encode()).hexdigest()[:12] if old.get("url") else "")
        seen[old_key] = old
    rows = []
    for i, listing in enumerate(listings, 1):
        key = listing_key(listing)
        old = seen.get(key)
        first = (old or {}).get("first_seen") or (
            previous["snapshot"] if old else today)
        rows.append(_row(f"L{i}", listing, key,
                         _photos(listing, key, out_dir), first))
    data = {"snapshot": today, "listings": rows, "cfg": _config(),
            "portal_errors": dict(LAST_ERRORS)}
    (out_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False))
    page = TEMPLATE.read_text().replace(
        "__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    (out_dir / "index.html").write_text(page)
    files = {"data.json": str(out_dir / "data.json")}
    used = {p for r in rows for p in r["photos"]}
    files.update({p: str(out_dir / p) for p in sorted(used)})
    for old in (previous or {}).get("listings", []):
        for p in old.get("photos", []):
            if p not in used:
                files[p] = None
    (out_dir / "files.json").write_text(json.dumps(files, indent=1))
    new = [r for r in rows if r["first_seen"] == today and previous]
    by_zone = {}
    for r in rows:
        by_zone[r["zone"]] = by_zone.get(r["zone"], 0) + 1
    return {"listings": len(rows), "by_zone": by_zone,
            "previous_listings": len((previous or {}).get("listings", [])),
            "new": len(new), "photos": len(used),
            "removed_photos": sum(v is None for v in files.values()),
            "portal_errors": dict(LAST_ERRORS)}


def main(argv=None):
    """Command-line entry point."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="build")
    p.add_argument("--previous", help="Yesterday's data.json, if any")
    args = p.parse_args(argv)
    previous = None
    if args.previous and Path(args.previous).exists():
        previous = json.loads(Path(args.previous).read_text())
    print(json.dumps(build(args.out, previous), indent=1))


if __name__ == "__main__":
    main()
