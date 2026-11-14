"""Tools exposed to the conversational agent, plus their session state."""

import json
from dataclasses import asdict, fields, replace

from . import config, market
from .agent import analyze, analyze_all, fetch, filter_listings
from .listing import Listing
from .mortgage import LoanInputs
from .rental import REGIMES, RentalInputs
from .sources.bienici import SourceError

LOAN_KEYS = [f.name for f in fields(LoanInputs) if f.name != "price"]
RENTAL_KEYS = [f.name for f in fields(RentalInputs)]

_NUM = {"type": "number"}

TOOLS = [
    {
        "name": "search_listings",
        "description": (
            "Search flats for sale in Paris 8e, 16e Nord (75116) and 17e "
            "Sud (Ternes, Plaine Monceau), keep those matching the price "
            "and surface criteria, analyze and rank them with the user's "
            "current financing settings. Returns a short ranked list with "
            "listing ids. Source 'all' (default) searches Bien'ici and Figaro "
            "Immobilier and merges duplicates. SeLoger, PAP and LeBonCoin "
            "block automated access: for those, ask the user to paste the "
            "ad and use analyze_custom_listing. If live search fails, offer "
            "'demo' (fictional) data."),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_price": _NUM, "max_price": _NUM, "min_surface": _NUM,
                "zones": {"type": "array", "items": {
                    "type": "string", "enum": list(config.ZONES)}},
                "source": {"type": "string",
                           "enum": ["all", "bienici", "figaro", "demo"]},
                "price_tolerance_pct": _NUM,
            },
        },
    },
    {
        "name": "analyze_listing",
        "description": (
            "Full analysis of one listing already returned by "
            "search_listings: price vs neighbourhood (low/typical/high "
            "bar), mortgage simulation, legal rent and rental costs, "
            "taxes, yields, cash-flow and investment mark /10. The UI "
            "shows the price bar and mark to the user automatically."),
        "input_schema": {
            "type": "object",
            "properties": {"listing_id": {"type": "string"}},
            "required": ["listing_id"],
        },
    },
    {
        "name": "analyze_custom_listing",
        "description": (
            "Analyze a flat described by the user (e.g. pasted from "
            "SeLoger/LeBonCoin). Returns the same analysis as "
            "analyze_listing and registers it with a listing id."),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "price": _NUM, "surface": _NUM,
                "zone": {"type": "string", "enum": list(config.ZONES)},
                "quartier": {"type": "string", "enum": sorted(
                    config.MARKET_PRICE_M2)},
                "rooms": {"type": "integer"},
                "dpe": {"type": "string", "enum": list("ABCDEFG")},
                "floor": {"type": "integer"},
                "elevator": {"type": "boolean"},
                "construction_period": {
                    "type": "string", "enum": list(config.PERIOD_FACTOR)},
                "url": {"type": "string"},
            },
            "required": ["price", "surface", "zone"],
        },
    },
    {
        "name": "update_settings",
        "description": (
            "Change the user's mortgage and rental variables; they persist "
            "for the rest of the conversation. Loan keys: "
            + ", ".join(LOAN_KEYS) + " (annual_rate, insurance_rate, "
            "notary_rate, guarantee_rate in %). Rental keys: "
            + ", ".join(RENTAL_KEYS) + " (monthly_rent 0 = legal max; "
            "taxe_fonciere / copro_charges -1 = estimate; regime one of "
            + ", ".join(REGIMES) + "). Returns all current settings."),
        "input_schema": {
            "type": "object",
            "properties": {
                "loan": {"type": "object"},
                "rental": {"type": "object"},
            },
        },
    },
    {
        "name": "compare_listings",
        "description": "Side-by-side key figures of several listing ids.",
        "input_schema": {
            "type": "object",
            "properties": {"listing_ids": {
                "type": "array", "items": {"type": "string"}}},
            "required": ["listing_ids"],
        },
    },
    {
        "name": "market_reference",
        "description": (
            "Reference resale price per m2 and legal rent cap per m2 "
            "(furnished and unfurnished) for a zone or quartier."),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "enum": list(config.ZONES)},
                "quartier": {"type": "string"},
                "surface": _NUM,
            },
            "required": ["zone"],
        },
    },
]


def _r(value, digits=0):
    return round(float(value), digits) if digits else int(round(value))


def summarize(a):
    """Return a compact JSON-able summary of an Analysis."""
    li, p, lo, r, s = a.listing, a.price, a.loan, a.rental, a.score
    return {
        "title": li.title, "url": li.url, "source": li.source,
        "zone": li.zone, "quartier": li.quartier, "price": _r(li.price),
        "surface": li.surface, "rooms": li.rooms, "dpe": li.dpe,
        "floor": li.floor, "elevator": li.elevator,
        "bienici_district": li.district,
        "annual_condo_fees": li.annual_condo_fees,
        "price_already_reduced": li.price_decreased,
        "price_m2": _r(p.price_m2), "reference_m2": _r(p.reference_m2),
        "typical_range_m2": [_r(p.low_m2), _r(p.high_m2)],
        "price_vs_market_pct": _r(p.delta_pct, 1),
        "price_label": p.label,
        "mortgage": {
            "loan_amount": _r(lo.loan_amount),
            "monthly_payment": _r(lo.monthly_payment),
            "total_credit_cost": _r(lo.total_credit_cost),
            "notary_fees": _r(lo.notary_fees),
            "debt_ratio_pct": _r(lo.debt_ratio, 1),
        },
        "rental": {
            "legal_rent_cap_m2": _r(r.rent_cap_m2, 2),
            "legal_max_rent": _r(r.legal_max_rent),
            "rent_used": _r(r.monthly_rent),
            "tenant_charges_monthly": _r(r.recoverable_charges_monthly),
            "yearly_costs": {k: _r(v) for k, v in r.cost_breakdown.items()},
            "yearly_tax": _r(r.yearly_tax),
            "gross_yield_pct": _r(r.gross_yield, 2),
            "net_yield_pct": _r(r.net_yield, 2),
            "cashflow_month_before_tax": _r(r.monthly_cashflow_before_tax),
            "cashflow_month_after_tax": _r(r.monthly_cashflow_after_tax),
        },
        "score": s.total, "verdict": s.verdict,
        "score_components": s.components, "pros": s.pros, "cons": s.cons,
    }


class AgentSession:
    """Listings found so far and the user's financing settings."""

    def __init__(self):
        """Start with default settings and no listing."""
        self.loan = LoanInputs(price=0)
        self.rental = RentalInputs()
        self.listings = {}
        self.analyses = []  # Analysis objects to display, newest last
        self._next = 1

    def _register(self, listing):
        lid = f"L{self._next}"
        self._next += 1
        self.listings[lid] = listing
        return lid

    def _get(self, lid):
        if lid not in self.listings:
            raise KeyError(f"Unknown listing id {lid}. Known: "
                           f"{', '.join(self.listings) or 'none'}")
        return self.listings[lid]

    def search_listings(self, min_price=None, max_price=None,
                        min_surface=None, zones=None, source="all",
                        price_tolerance_pct=5):
        """Fetch, filter and rank listings."""
        crit = dict(config.SEARCH)
        for key, val in (("min_price", min_price), ("max_price", max_price),
                         ("min_surface", min_surface)):
            if val is not None:
                crit[key] = val
        tol = (price_tolerance_pct or 0) / 100
        try:
            raw = fetch(source, criteria={
                "min_price": crit["min_price"] * (1 - tol),
                "max_price": crit["max_price"] * (1 + tol),
                "min_surface": crit["min_surface"]})
        except SourceError as exc:
            return {"error": str(exc), "hint": "Offer demo data or manual "
                    "entry with analyze_custom_listing."}
        kept = [x for x in filter_listings(raw, crit, tol)
                if not zones or x.zone in zones]
        results = analyze_all(kept, self.loan, self.rental)
        rows = []
        for a in results:
            lid = self._register(a.listing)
            rows.append({"id": lid, "title": a.listing.title,
                         "portals": a.listing.source,
                         "zone": a.listing.zone,
                         "quartier": a.listing.quartier,
                         "price": _r(a.listing.price),
                         "surface": a.listing.surface,
                         "dpe": a.listing.dpe,
                         "price_label": a.price.label,
                         "vs_market_pct": _r(a.price.delta_pct, 1),
                         "net_yield_pct": _r(a.rental.net_yield, 2),
                         "cashflow_after_tax": _r(
                             a.rental.monthly_cashflow_after_tax),
                         "score": a.score.total})
        from .agent import LAST_ERRORS
        out = {"source": source, "criteria": crit, "found": len(rows),
               "listings": rows[:15]}
        if LAST_ERRORS:
            out["portal_errors"] = dict(LAST_ERRORS)
        return out

    def analyze_listing(self, listing_id):
        """Analyze a stored listing with the current settings."""
        a = analyze(self._get(listing_id), self.loan, self.rental)
        self.analyses.append(a)
        return {"id": listing_id, **summarize(a)}

    def analyze_custom_listing(self, price, surface, zone, **kw):
        """Register and analyze a listing described by the user."""
        quartier = kw.pop("quartier", None)
        if quartier not in config.ZONES[zone]["quartiers"]:
            quartier = None
        listing = Listing(title=kw.pop("title", None) or "User listing",
                          price=price, surface=surface, zone=zone,
                          postal_code=config.ZONES[zone]["postal_code"],
                          quartier=quartier, source="user", **kw)
        market.locate(listing)
        listing.zone = zone
        return self.analyze_listing(self._register(listing))

    def update_settings(self, loan=None, rental=None):
        """Update persistent financing / rental variables."""
        unknown = [k for k in (loan or {}) if k not in LOAN_KEYS]
        unknown += [k for k in (rental or {}) if k not in RENTAL_KEYS]
        if unknown:
            raise ValueError(f"Unknown setting(s): {unknown}")
        if rental and rental.get("regime", REGIMES[0]) not in REGIMES:
            raise ValueError(f"regime must be one of {REGIMES}")
        self.loan = replace(self.loan, **(loan or {}))
        self.rental = replace(self.rental, **(rental or {}))
        return self.settings()

    def settings(self):
        """Return the current settings."""
        loan = asdict(self.loan)
        loan.pop("price")
        return {"loan": loan, "rental": asdict(self.rental)}

    def compare_listings(self, listing_ids):
        """Return key figures of several listings."""
        out = []
        for lid in listing_ids:
            s = summarize(analyze(self._get(lid), self.loan, self.rental))
            out.append({"id": lid, "title": s["title"], "price": s["price"],
                        "surface": s["surface"], "dpe": s["dpe"],
                        "price_label": s["price_label"],
                        "vs_market_pct": s["price_vs_market_pct"],
                        "rent": s["rental"]["rent_used"],
                        "net_yield_pct": s["rental"]["net_yield_pct"],
                        "cashflow_after_tax":
                            s["rental"]["cashflow_month_after_tax"],
                        "score": s["score"], "verdict": s["verdict"]})
        return {"comparison": out}

    def market_reference(self, zone, quartier=None, surface=20.0):
        """Return reference price and rent caps."""
        from .rental import legal_rent_cap_m2
        if quartier not in config.ZONES[zone]["quartiers"]:
            quartier = None
        caps = {f: _r(legal_rent_cap_m2(zone, quartier, 1, "avant 1946",
                                        f == "furnished"), 2)
                for f in ("furnished", "unfurnished")}
        return {"zone": zone, "quartier": quartier,
                "reference_price_m2": _r(market.reference_price_m2(
                    zone, quartier, surface)),
                "rent_cap_m2_1room_pre1946": caps,
                "note": "Approximate figures; verify on DVF and "
                        "referenceloyer.drihl.ile-de-france.gouv.fr."}

    def execute(self, name, args):
        """Run a tool by name; return (json_text, is_error)."""
        handler = getattr(self, name, None)
        if name not in {t["name"] for t in TOOLS} or handler is None:
            return json.dumps({"error": f"Unknown tool {name}"}), True
        try:
            result = handler(**(args or {}))
        except (KeyError, ValueError, TypeError) as exc:
            return json.dumps({"error": str(exc)}), True
        return json.dumps(result, ensure_ascii=False, default=str), False
