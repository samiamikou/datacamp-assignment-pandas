"""Load listings from a CSV file (manual copy from SeLoger, LeBonCoin...).

Required columns: title, price, surface, postal_code.
Optional: rooms, quartier, dpe, floor, elevator, construction_period,
url, lat, lon, description.
"""

from pathlib import Path

import pandas as pd

from ..listing import Listing

DEMO_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.csv"
OPTIONAL = ["rooms", "quartier", "dpe", "floor", "elevator",
            "construction_period", "url", "lat", "lon", "description"]


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def _row_to_listing(row, source):
    kwargs = {k: _clean(row.get(k)) for k in OPTIONAL}
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    for key in ("rooms", "floor"):
        if key in kwargs:
            kwargs[key] = int(kwargs[key])
    if "elevator" in kwargs:
        kwargs["elevator"] = str(kwargs["elevator"]).lower() in (
            "1", "true", "yes", "oui")
    return Listing(title=str(row["title"]), price=float(row["price"]),
                   surface=float(row["surface"]),
                   postal_code=str(row["postal_code"]).split(".")[0],
                   source=source, **kwargs)


def load_csv(path_or_buffer, source="csv"):
    """Return the listings contained in a CSV file."""
    df = pd.read_csv(path_or_buffer, dtype={"postal_code": str})
    missing = {"title", "price", "surface", "postal_code"} - set(df)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    return [_row_to_listing(row, source)
            for row in df.to_dict(orient="records")]


def load_demo():
    """Return the bundled fictional demo listings."""
    return load_csv(DEMO_PATH, source="demo")
