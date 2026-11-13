"""Agent: retrieve listings, filter, simulate and rank them.

Usage::

    python -m apartment_analyzer.agent --source bienici --out deals.csv
    python -m apartment_analyzer.agent --source demo
    python -m apartment_analyzer.agent --source csv --csv my_list.csv
"""

import argparse
from collections import defaultdict
from dataclasses import dataclass, replace

import pandas as pd

from . import config, market
from .mortgage import LoanInputs, simulate_loan
from .rental import RentalInputs, simulate_rental
from .scoring import score_investment
from .sources import bienici
from .sources.csv_source import load_csv, load_demo


@dataclass
class Analysis:
    """Everything computed for one listing."""

    listing: object
    price: object
    loan: object
    rental: object
    score: object


def fetch(source="bienici", csv_path=None, criteria=None):
    """Return raw listings from the chosen source."""
    if source == "demo":
        return load_demo()
    if source == "csv":
        return load_csv(csv_path)
    crit = criteria or config.SEARCH
    listings = []
    for zone in config.ZONES.values():
        listings += bienici.search(zone["postal_code"],
                                   crit["min_price"], crit["max_price"],
                                   crit["min_surface"])
    return listings


def filter_listings(listings, criteria=None, price_tolerance=0.0):
    """Keep listings in the target zones matching the criteria."""
    crit = criteria or config.SEARCH
    lo = crit["min_price"] * (1 - price_tolerance)
    hi = crit["max_price"] * (1 + price_tolerance)
    kept, seen = [], set()
    for item in listings:
        key = (item.url or item.title, item.price, item.surface)
        if key in seen or item.surface < crit["min_surface"]:
            continue
        if lo <= item.price <= hi and market.locate(item):
            kept.append(item)
            seen.add(key)
    return kept


def analyze(listing, loan_params=None, rental_params=None, peers_m2=None):
    """Run price assessment, mortgage, rental and scoring on a listing."""
    if listing.zone is None and not market.locate(listing):
        raise ValueError("Listing outside 8e / 16e Nord / 17e Sud.")
    loan_inp = replace(loan_params or LoanInputs(price=0),
                       price=listing.price)
    loan = simulate_loan(loan_inp)
    rental = simulate_rental(listing, rental_params or RentalInputs(),
                             loan, loan_inp)
    price = market.assess_price(listing, peers_m2)
    return Analysis(listing, price, loan, rental,
                    score_investment(listing, price, rental))


def analyze_all(listings, loan_params=None, rental_params=None):
    """Analyze listings, using same-quartier peers for price context."""
    peers = defaultdict(list)
    for item in listings:
        peers[(item.zone, item.quartier)].append(item.price_m2)
    results = [analyze(i, loan_params, rental_params,
                       peers[(i.zone, i.quartier)]) for i in listings]
    return sorted(results, key=lambda a: a.score.total, reverse=True)


def to_dataframe(results):
    """Return a summary table of analyses."""
    rows = []
    for a in results:
        row = a.listing.to_dict()
        row.pop("photos", None)
        row.pop("description", None)
        row.update({
            "ref_price_m2": round(a.price.reference_m2),
            "price_vs_market_pct": round(a.price.delta_pct, 1),
            "price_label": a.price.label,
            "legal_rent": round(a.rental.monthly_rent),
            "gross_yield_pct": round(a.rental.gross_yield, 2),
            "net_yield_pct": round(a.rental.net_yield, 2),
            "monthly_payment": round(a.loan.monthly_payment),
            "cashflow_after_tax": round(
                a.rental.monthly_cashflow_after_tax),
            "score": a.score.total,
            "verdict": a.score.verdict,
        })
        rows.append(row)
    return pd.DataFrame(rows)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", choices=["bienici", "csv", "demo"],
                   default="bienici")
    p.add_argument("--csv", help="CSV file when --source csv")
    p.add_argument("--down-payment", type=float, default=25_000)
    p.add_argument("--rate", type=float, default=3.2)
    p.add_argument("--years", type=int, default=25)
    p.add_argument("--tmi", type=float, default=30.0)
    p.add_argument("--unfurnished", action="store_true")
    p.add_argument("--tolerance", type=float, default=0.05,
                   help="Accepted price overshoot, e.g. 0.05 = 5%%")
    p.add_argument("--out", help="Write the ranking to this CSV file")
    return p.parse_args(argv)


def main(argv=None):
    """Command-line entry point."""
    args = _parse_args(argv)
    listings = filter_listings(fetch(args.source, args.csv),
                               price_tolerance=args.tolerance)
    loan = LoanInputs(price=0, down_payment=args.down_payment,
                      annual_rate=args.rate, years=args.years)
    rental = RentalInputs(furnished=not args.unfurnished, tmi=args.tmi)
    df = to_dataframe(analyze_all(listings, loan, rental))
    cols = ["score", "verdict", "title", "zone", "quartier", "price",
            "surface", "price_m2", "price_label", "price_vs_market_pct",
            "legal_rent", "net_yield_pct", "cashflow_after_tax", "url"]
    with pd.option_context("display.width", 200,
                           "display.max_colwidth", 40):
        print(df[cols].to_string(index=False) if len(df) else
              "No listing matches the criteria.")
    if args.out:
        df.to_csv(args.out, index=False)
    return df


if __name__ == "__main__":
    main()
