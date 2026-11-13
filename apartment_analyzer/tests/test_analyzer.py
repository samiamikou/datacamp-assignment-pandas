"""Unit tests for the apartment analyzer (no network)."""

import pytest

from apartment_analyzer import market
from apartment_analyzer.agent import analyze, analyze_all, filter_listings
from apartment_analyzer.listing import Listing
from apartment_analyzer.mortgage import LoanInputs, monthly_payment, \
    simulate_loan
from apartment_analyzer.pricebar import bar_position, price_bar_html
from apartment_analyzer.rental import RentalInputs, legal_rent_cap_m2
from apartment_analyzer.sources.csv_source import load_demo


def _flat(**kw):
    base = dict(title="Studio Ternes", price=220_000, surface=20.0,
                postal_code="75017", quartier="Ternes", dpe="D", floor=3,
                elevator=True)
    base.update(kw)
    return Listing(**base)


def test_monthly_payment_known_value():
    """Check 200k over 20 years at 3% (~1109.20 EUR)."""
    assert monthly_payment(200_000, 3.0, 20) == pytest.approx(1109.20, 0.01)
    assert monthly_payment(120_000, 0.0, 10) == pytest.approx(1000)


def test_schedule_repays_loan():
    """Check the schedule repays the whole principal."""
    res = simulate_loan(LoanInputs(price=220_000, down_payment=20_000))
    assert res.schedule["principal"].sum() == pytest.approx(res.loan_amount)
    assert res.schedule["balance"].iloc[-1] == pytest.approx(0, abs=1e-6)


def test_zones_and_17_sud():
    """Check zone detection and exclusion of north 17e."""
    assert market.locate(_flat())
    north = _flat(quartier=None, lat=48.8900, lon=2.3190)
    assert not market.locate(north)
    assert not market.locate(_flat(postal_code="75016"))
    assert not market.locate(_flat(description="pres de Batignolles"))
    keyword = _flat(title="Studio", quartier=None,
                    description="metro Villiers")
    assert market.locate(keyword)
    assert keyword.quartier == "Plaine-de-Monceaux"


def test_price_assessment_labels():
    """Check low / typical / high labels."""
    f = _flat()
    market.locate(f)
    ref = market.reference_price_m2(f.zone, f.quartier, f.surface)
    for ratio, label in [(0.85, "low"), (1.0, "typical"), (1.2, "high")]:
        f.price = ref * ratio * f.surface
        assert market.assess_price(f).label == label


def test_legal_rent_furnished_higher():
    """Check furnished cap is higher than unfurnished."""
    vide = legal_rent_cap_m2("17e Sud", "Ternes", 1, "avant 1946", False)
    meuble = legal_rent_cap_m2("17e Sud", "Ternes", 1, "avant 1946", True)
    assert meuble > vide > 30


def test_analyze_and_score_bounds():
    """Check full analysis outputs are consistent."""
    a = analyze(_flat(), LoanInputs(price=0), RentalInputs())
    assert 0 <= a.score.total <= 10
    assert a.rental.monthly_rent == pytest.approx(a.rental.legal_max_rent)
    g = analyze(_flat(dpe="G"), LoanInputs(price=0), RentalInputs())
    assert g.score.total <= 4.0


def test_demo_pipeline():
    """Check the demo pipeline filters and ranks listings."""
    kept = filter_listings(load_demo())
    assert all(200_000 <= x.price <= 250_000 for x in kept)
    assert not any("Batignolles" in x.title for x in kept)
    results = analyze_all(kept)
    scores = [r.score.total for r in results]
    assert scores == sorted(scores, reverse=True)


def test_price_bar_html():
    """Check the marker position and HTML output."""
    assert bar_position(1, 100, 200) == 2.0
    f = _flat()
    market.locate(f)
    assert "neighbourhood" in price_bar_html(market.assess_price(f))
