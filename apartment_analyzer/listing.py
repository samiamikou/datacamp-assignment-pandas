"""Common listing model shared by every data source."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Listing:
    """A flat for sale."""

    title: str
    price: float
    surface: float
    postal_code: str
    rooms: int = 1
    zone: Optional[str] = None
    quartier: Optional[str] = None
    dpe: Optional[str] = None
    floor: Optional[int] = None
    elevator: Optional[bool] = None
    construction_period: str = "avant 1946"
    url: str = ""
    source: str = "manual"
    lat: Optional[float] = None
    lon: Optional[float] = None
    description: str = ""
    district: Optional[str] = None
    annual_condo_fees: Optional[float] = None
    price_decreased: bool = False
    photos: list = field(default_factory=list)

    @property
    def price_m2(self):
        """Return the price per square meter."""
        return self.price / self.surface if self.surface else float("nan")

    def to_dict(self):
        """Return the listing as a plain dict."""
        data = asdict(self)
        data["price_m2"] = round(self.price_m2)
        return data
