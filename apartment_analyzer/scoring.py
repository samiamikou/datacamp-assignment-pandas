"""Investment mark /10 with explained pros and cons."""

from dataclasses import dataclass, field

from . import config

WEIGHTS = {"price": 0.35, "yield": 0.20, "cashflow": 0.15,
           "dpe": 0.20, "liquidity": 0.10}


@dataclass
class Score:
    """Final investment mark and its explanation."""

    total: float
    verdict: str
    components: dict
    pros: list = field(default_factory=list)
    cons: list = field(default_factory=list)


def _clip(value, low=0.0, high=10.0):
    return max(low, min(high, value))


def _lerp(x, x0, x1):
    """Map x linearly from [x0, x1] onto [0, 10]."""
    return _clip((x - x0) / (x1 - x0) * 10)


def price_score(delta_pct):
    """Return 10 for -15% under market, 6 at market, 0 at +22%."""
    if delta_pct <= 0:
        return _clip(6 + -delta_pct / 15 * 4)
    return _clip(6 - delta_pct / 22 * 6)


def yield_score(net_yield):
    """Score a net yield (Paris studios: ~3% typical)."""
    return _lerp(net_yield, 2.0, 4.5)


def cashflow_score(monthly_cf):
    """Score the monthly after-tax cash-flow."""
    return _lerp(monthly_cf, -450.0, 50.0)


def dpe_score(dpe):
    """Score the energy label and return (score, comment)."""
    return config.DPE_RULES.get((dpe or "").upper(),
                                (5, "Energy label unknown: ask for it."))


def liquidity_score(listing):
    """Score resale/rental ease (surface, floor, elevator)."""
    score = 6.0
    if listing.surface >= 25:
        score += 1
    if listing.elevator:
        score += 1.5
    if listing.floor == 0:
        score -= 2.5
    elif listing.floor is not None and listing.floor >= 5 \
            and listing.elevator is False:
        score -= 2
    elif listing.floor is not None and listing.floor >= 2:
        score += 1
    return _clip(score)


def _verdict(total):
    if total >= 7.5:
        return "Excellent investment"
    if total >= 6.0:
        return "Good investment"
    if total >= 4.5:
        return "Average - negotiate"
    return "Not recommended"


def _explain(price, rental, dpe_comment, pros, cons):
    if price.label == "low":
        pros.append(f"Price {abs(price.delta_pct):.0f}% below the "
                    "neighbourhood reference.")
    elif price.label == "high":
        cons.append(f"Price {price.delta_pct:.0f}% above the "
                    "neighbourhood reference: negotiate.")
    if rental.net_yield >= 3.5:
        pros.append(f"Solid net yield ({rental.net_yield:.1f}%).")
    elif rental.net_yield < 2.8:
        cons.append(f"Low net yield ({rental.net_yield:.1f}%).")
    cf = rental.monthly_cashflow_after_tax
    (pros if cf >= 0 else cons).append(
        f"Monthly cash-flow after tax: {cf:+.0f} EUR.")
    (pros if "Excellent" in dpe_comment or "good" in dpe_comment.lower()
     else cons).append(dpe_comment)


def score_investment(listing, price, rental):
    """Return the investment Score of a listing."""
    dpe_val, dpe_comment = dpe_score(listing.dpe)
    comps = {
        "price": price_score(price.delta_pct),
        "yield": yield_score(rental.net_yield),
        "cashflow": cashflow_score(rental.monthly_cashflow_after_tax),
        "dpe": float(dpe_val),
        "liquidity": liquidity_score(listing),
    }
    total = sum(WEIGHTS[k] * v for k, v in comps.items())
    if (listing.dpe or "").upper() == "G":
        total = min(total, 4.0)  # cannot legally be rented as is
    pros, cons = [], []
    _explain(price, rental, dpe_comment, pros, cons)
    return Score(total=round(total, 1), verdict=_verdict(total),
                 components={k: round(v, 1) for k, v in comps.items()},
                 pros=pros, cons=cons)
