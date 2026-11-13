"""Rental simulation: legal rent (encadrement), costs, taxes, cash-flow."""

from dataclasses import dataclass

from . import config

REGIMES = ["LMNP reel", "LMNP micro-BIC", "Nu micro-foncier", "Nu reel"]


@dataclass
class RentalInputs:
    """User-defined rental parameters (yearly EUR unless stated)."""

    furnished: bool = True
    monthly_rent: float = 0.0          # 0 -> use the legal maximum
    rent_cap_m2: float = 0.0           # 0 -> use config table
    taxe_fonciere: float = -1.0        # <0 -> estimate from surface
    copro_charges: float = -1.0        # <0 -> estimate from surface
    non_recoverable_share: float = config.NON_RECOVERABLE_SHARE
    pno_insurance: float = 150.0
    gli_rate: float = 0.0              # unpaid-rent insurance, % of rent
    management_rate: float = 0.0       # agency management, % of rent
    vacancy_months: float = 1.0
    maintenance_rate: float = 3.0      # % of rent set aside for repairs
    regime: str = "LMNP reel"
    tmi: float = 30.0                  # marginal income-tax rate, %
    social_rate: float = 17.2          # prelevements sociaux, %


@dataclass
class RentalResult:
    """Output of the rental simulation."""

    rent_cap_m2: float
    legal_max_rent: float
    monthly_rent: float
    recoverable_charges_monthly: float
    yearly_rent_collected: float
    yearly_costs: float
    cost_breakdown: dict
    yearly_tax: float
    gross_yield: float
    net_yield: float
    monthly_cashflow_before_tax: float
    monthly_cashflow_after_tax: float


def legal_rent_cap_m2(zone, quartier, rooms, period, furnished):
    """Return the rent-control ceiling in EUR per m2 per month."""
    base = config.RENT_CAP_M2_BASE.get(quartier)
    if base is None:
        base = config.ZONE_RENT_CAP_M2[zone]
    base *= config.ROOMS_FACTOR.get(min(max(rooms, 1), 3), 1.0)
    base *= config.PERIOD_FACTOR.get(period, 1.0)
    if furnished:
        base *= config.FURNISHED_FACTOR
    return base


def _taxable_income(regime, rent, deductible, amortization):
    if regime == "LMNP micro-BIC":
        return rent * 0.5
    if regime == "Nu micro-foncier":
        return rent * 0.7
    if regime == "LMNP reel":
        # Amortization cannot create a deficit (carried forward).
        return max(rent - deductible - amortization, 0.0)
    return max(rent - deductible, 0.0)


def yearly_tax(regime, rent, deductible, amortization, tmi, social):
    """Return income tax + social contributions on rental income."""
    base = _taxable_income(regime, rent, deductible, amortization)
    return base * (tmi + social) / 100


def _running_costs(inp, listing, rent_year):
    tf = inp.taxe_fonciere
    if tf < 0:
        tf = config.TAXE_FONCIERE_M2 * listing.surface
    copro = inp.copro_charges
    if copro < 0:
        copro = listing.annual_condo_fees or \
            config.COPRO_CHARGES_M2 * listing.surface
    return {
        "Taxe fonciere": tf,
        "Copro (non recoverable)": copro * inp.non_recoverable_share,
        "PNO insurance": inp.pno_insurance,
        "GLI insurance": rent_year * inp.gli_rate / 100,
        "Management": rent_year * inp.management_rate / 100,
        "Maintenance reserve": rent_year * inp.maintenance_rate / 100,
    }, copro * (1 - inp.non_recoverable_share)


def simulate_rental(listing, inp, loan, loan_inputs):
    """Simulate the yearly economics of renting the flat out."""
    cap_m2 = inp.rent_cap_m2 or legal_rent_cap_m2(
        listing.zone, listing.quartier, listing.rooms,
        listing.construction_period, inp.furnished)
    legal_max = cap_m2 * listing.surface
    rent = inp.monthly_rent or legal_max
    rent_year = rent * max(12 - inp.vacancy_months, 0)
    costs, recoverable = _running_costs(inp, listing, rent_year)
    yearly_costs = sum(costs.values())

    first_year_interest = float(loan.schedule["interest"].iloc[0]) \
        if len(loan.schedule) else 0.0
    loan_ins_year = loan.monthly_insurance * 12
    deductible = yearly_costs + first_year_interest + loan_ins_year
    amortization = (0.85 * (loan_inputs.price + loan.notary_fees) / 30
                    + loan_inputs.works / 15
                    + loan_inputs.furniture / 7)
    tax = yearly_tax(inp.regime, rent_year, deductible, amortization,
                     inp.tmi, inp.social_rate)

    invested = loan.total_cost_project
    cf_before = (rent_year - yearly_costs) / 12 - loan.monthly_payment
    return RentalResult(
        rent_cap_m2=cap_m2, legal_max_rent=legal_max, monthly_rent=rent,
        recoverable_charges_monthly=recoverable / 12,
        yearly_rent_collected=rent_year, yearly_costs=yearly_costs,
        cost_breakdown=costs, yearly_tax=tax,
        gross_yield=rent * 12 / listing.price * 100,
        net_yield=(rent_year - yearly_costs) / invested * 100,
        monthly_cashflow_before_tax=cf_before,
        monthly_cashflow_after_tax=cf_before - tax / 12)
