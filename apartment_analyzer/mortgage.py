"""Mortgage simulation (French fixed-rate loan)."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class LoanInputs:
    """User-defined financing parameters."""

    price: float
    down_payment: float = 25_000
    annual_rate: float = 3.2
    years: int = 25
    insurance_rate: float = 0.30
    notary_rate: float = 8.0
    agency_fees: float = 0.0
    works: float = 0.0
    furniture: float = 0.0
    guarantee_rate: float = 1.0
    bank_fees: float = 1_000.0
    monthly_income: float = 0.0
    other_monthly_debt: float = 0.0


@dataclass
class LoanResult:
    """Output of the mortgage simulation."""

    total_cost_project: float
    notary_fees: float
    loan_amount: float
    monthly_principal_interest: float
    monthly_insurance: float
    monthly_payment: float
    total_interest: float
    total_insurance: float
    total_credit_cost: float
    debt_ratio: float
    schedule: pd.DataFrame


def monthly_payment(principal, annual_rate, years):
    """Return the constant monthly payment of an amortizing loan."""
    n = int(years * 12)
    if principal <= 0 or n <= 0:
        return 0.0
    r = annual_rate / 100 / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def amortization_schedule(principal, annual_rate, years):
    """Return a yearly amortization table."""
    payment = monthly_payment(principal, annual_rate, years)
    r = annual_rate / 100 / 12
    balance, rows = principal, []
    for month in range(1, int(years * 12) + 1):
        interest = balance * r
        capital = payment - interest
        balance = max(balance - capital, 0.0)
        rows.append((month, (month - 1) // 12 + 1, interest, capital,
                     balance))
    df = pd.DataFrame(rows, columns=["month", "year", "interest",
                                     "principal", "balance"])
    return df.groupby("year").agg(
        interest=("interest", "sum"), principal=("principal", "sum"),
        balance=("balance", "last")).reset_index()


def simulate_loan(inp):
    """Run the full mortgage simulation."""
    notary = inp.price * inp.notary_rate / 100
    project = (inp.price + notary + inp.agency_fees + inp.works
               + inp.furniture + inp.bank_fees)
    base_loan = max(project - inp.down_payment, 0.0)
    # The guarantee (Credit Logement / caution) is financed by the loan.
    loan = base_loan * (1 + inp.guarantee_rate / 100)
    pi = monthly_payment(loan, inp.annual_rate, inp.years)
    ins = loan * inp.insurance_rate / 100 / 12
    total_interest = pi * inp.years * 12 - loan
    total_ins = ins * inp.years * 12
    debt_ratio = 0.0
    if inp.monthly_income > 0:
        debt_ratio = (pi + ins + inp.other_monthly_debt) \
            / inp.monthly_income * 100
    return LoanResult(
        total_cost_project=project + loan - base_loan,
        notary_fees=notary, loan_amount=loan,
        monthly_principal_interest=pi, monthly_insurance=ins,
        monthly_payment=pi + ins, total_interest=total_interest,
        total_insurance=total_ins,
        total_credit_cost=total_interest + total_ins + loan - base_loan
        + inp.bank_fees,
        debt_ratio=debt_ratio,
        schedule=amortization_schedule(loan, inp.annual_rate, inp.years))
