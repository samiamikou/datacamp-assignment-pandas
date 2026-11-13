"""Streamlit UI.  Run with:  streamlit run apartment_analyzer/app.py."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apartment_analyzer import config, market  # noqa: E402
from apartment_analyzer.agent import (analyze, analyze_all, fetch,  # noqa
                                      filter_listings, to_dataframe)
from apartment_analyzer.listing import Listing  # noqa: E402
from apartment_analyzer.mortgage import LoanInputs  # noqa: E402
from apartment_analyzer.pricebar import price_bar_html  # noqa: E402
from apartment_analyzer.rental import REGIMES, RentalInputs  # noqa: E402
from apartment_analyzer.sources.bienici import SourceError  # noqa: E402
from apartment_analyzer.sources.csv_source import load_csv  # noqa: E402

st.set_page_config(page_title="Paris flat investment", layout="wide")


def eur(value):
    """Format a number as euros."""
    return f"{value:,.0f} EUR".replace(",", " ")


@st.cache_data(ttl=3600, show_spinner="Searching Bien'ici...")
def cached_fetch(min_price, max_price, min_surface):
    """Fetch live listings, cached one hour."""
    return fetch("bienici", criteria={"min_price": min_price,
                                      "max_price": max_price,
                                      "min_surface": min_surface})


def sidebar_search():
    """Render search inputs and return (source, criteria, ...)."""
    st.sidebar.header("1. Search")
    source = st.sidebar.radio(
        "Source", ["Bien'ici (live)", "Upload CSV", "Demo data"])
    upload = None
    if source == "Upload CSV":
        upload = st.sidebar.file_uploader("CSV of listings", type="csv")
    price = st.sidebar.slider("Price (EUR)", 150_000, 300_000,
                              (config.SEARCH["min_price"],
                               config.SEARCH["max_price"]), 5_000)
    tol = st.sidebar.slider("Tolerance around the price (%)", 0, 15, 5)
    surface = st.sidebar.number_input("Min surface (m2)", 9.0, 100.0,
                                      config.SEARCH["min_surface"])
    zones = st.sidebar.multiselect("Zones", list(config.ZONES),
                                   list(config.ZONES))
    crit = {"min_price": price[0], "max_price": price[1],
            "min_surface": surface}
    return source, upload, crit, tol / 100, zones


def sidebar_loan():
    """Render mortgage inputs."""
    st.sidebar.header("2. Mortgage")
    s = st.sidebar
    return LoanInputs(
        price=0,
        down_payment=s.number_input("Down payment (EUR)", 0, 500_000,
                                    25_000, 1_000),
        annual_rate=s.number_input("Interest rate (%/yr)", 0.0, 10.0,
                                   3.2, 0.05),
        years=s.slider("Duration (years)", 5, 30, 25),
        insurance_rate=s.number_input("Borrower insurance (%/yr)", 0.0,
                                      1.0, 0.30, 0.01),
        notary_rate=s.number_input("Notary fees (% of price)", 0.0, 12.0,
                                   8.0, 0.1),
        agency_fees=s.number_input("Agency fees if not included", 0, 50_000,
                                   0, 500),
        works=s.number_input("Renovation works (EUR)", 0, 200_000, 0, 1_000),
        furniture=s.number_input("Furniture (EUR)", 0, 30_000, 4_000, 500),
        guarantee_rate=s.number_input("Guarantee / caution (%)", 0.0, 3.0,
                                      1.0, 0.1),
        bank_fees=s.number_input("Bank fees (EUR)", 0, 5_000, 1_000, 100),
        monthly_income=s.number_input("Your net monthly income (EUR)", 0,
                                      50_000, 0, 100),
        other_monthly_debt=s.number_input("Other monthly loans (EUR)", 0,
                                          10_000, 0, 50))


def sidebar_rental():
    """Render rental inputs."""
    st.sidebar.header("3. Rental")
    s = st.sidebar
    furnished = s.toggle("Furnished (meuble)", True)
    regime = s.selectbox("Tax regime", REGIMES,
                         index=0 if furnished else 2)
    return RentalInputs(
        furnished=furnished,
        monthly_rent=s.number_input("Rent override (0 = legal max)", 0,
                                    5_000, 0, 10),
        taxe_fonciere=s.number_input("Taxe fonciere/yr (-1 = estimate)",
                                     -1, 5_000, -1, 50),
        copro_charges=s.number_input("Copro charges/yr (-1 = estimate)",
                                     -1, 10_000, -1, 50),
        pno_insurance=s.number_input("PNO insurance/yr", 0, 1_000, 150, 10),
        gli_rate=s.number_input("Unpaid-rent insurance GLI (% rent)", 0.0,
                                5.0, 0.0, 0.5),
        management_rate=s.number_input("Agency management (% rent)", 0.0,
                                       12.0, 0.0, 0.5),
        vacancy_months=s.number_input("Vacancy (months/yr)", 0.0, 6.0,
                                      1.0, 0.5),
        maintenance_rate=s.number_input("Maintenance reserve (% rent)",
                                        0.0, 15.0, 3.0, 0.5),
        regime=regime,
        tmi=s.selectbox("Marginal tax rate TMI (%)",
                        [0.0, 11.0, 30.0, 41.0, 45.0], index=2),
        social_rate=s.number_input("Social contributions (%)", 0.0, 25.0,
                                   17.2, 0.1))


def load_listings(source, upload, crit, tol, zones):
    """Return filtered listings for the chosen source."""
    try:
        if source == "Demo data":
            raw = fetch("demo")
        elif source == "Upload CSV":
            raw = load_csv(upload) if upload else []
        else:
            raw = cached_fetch(crit["min_price"] * (1 - tol),
                               crit["max_price"] * (1 + tol),
                               crit["min_surface"])
    except (SourceError, ValueError) as exc:
        st.error(f"{exc}\n\nUse 'Upload CSV' or 'Analyze one listing'.")
        return []
    kept = filter_listings(raw, crit, tol)
    return [x for x in kept if x.zone in zones]


def show_score(a):
    """Render the investment mark."""
    s = a.score
    color = "#188038" if s.total >= 6 else (
        "#b06000" if s.total >= 4.5 else "#c5221f")
    st.markdown(
        f"<div style='font-size:46px;font-weight:800;color:{color}'>"
        f"{s.total}/10</div><div style='font-size:20px;color:{color}'>"
        f"{s.verdict}</div>", unsafe_allow_html=True)
    comp = pd.DataFrame({"criterion": list(s.components),
                         "score /10": list(s.components.values())})
    st.dataframe(comp, hide_index=True, use_container_width=True)
    for p in s.pros:
        st.markdown(f"+ {p}")
    for c in s.cons:
        st.markdown(f"- {c}")


def show_loan(a, loan_inp):
    """Render the mortgage simulation."""
    lo = a.loan
    c = st.columns(4)
    c[0].metric("Loan amount", eur(lo.loan_amount))
    c[1].metric("Monthly payment", eur(lo.monthly_payment),
                f"incl. insurance {eur(lo.monthly_insurance)}",
                delta_color="off")
    c[2].metric("Total credit cost", eur(lo.total_credit_cost))
    c[3].metric("Total project", eur(lo.total_cost_project))
    if loan_inp.monthly_income:
        ratio = lo.debt_ratio
        msg = f"Debt ratio: {ratio:.1f}% (HCSF limit 35%)"
        (st.success if ratio <= 35 else st.warning)(msg)
    sched = lo.schedule.set_index("year")
    st.bar_chart(sched[["principal", "interest"]], height=220)
    with st.expander("Amortization table"):
        st.dataframe(sched.round(0), use_container_width=True)


def show_rental(a):
    """Render the rental simulation."""
    r = a.rental
    c = st.columns(4)
    c[0].metric("Legal max rent (HC)", eur(r.legal_max_rent),
                f"{r.rent_cap_m2:.1f} EUR/m2", delta_color="off")
    c[1].metric("Rent used", eur(r.monthly_rent),
                f"+ charges {eur(r.recoverable_charges_monthly)}",
                delta_color="off")
    c[2].metric("Gross / net yield",
                f"{r.gross_yield:.2f}% / {r.net_yield:.2f}%")
    c[3].metric("Cash-flow / month after tax",
                eur(r.monthly_cashflow_after_tax),
                f"before tax {eur(r.monthly_cashflow_before_tax)}",
                delta_color="off")
    rows = [("Rent collected (after vacancy)", r.yearly_rent_collected)]
    rows += [(k, -v) for k, v in r.cost_breakdown.items()]
    rows += [("Loan payments", -a.loan.monthly_payment * 12),
             ("Income tax + social", -r.yearly_tax)]
    df = pd.DataFrame(rows, columns=["Yearly item", "EUR"])
    df.loc[len(df)] = ["NET CASH-FLOW", df["EUR"].sum()]
    st.dataframe(df.round(0), hide_index=True, use_container_width=True)
    st.caption("Legal rent = loyer de reference majore (encadrement des "
               "loyers Paris). Verify on referenceloyer.drihl.ile-de-france"
               ".gouv.fr. Recoverable charges are paid by the tenant.")


def show_detail(a, loan_inp):
    """Render the full analysis of one listing."""
    li = a.listing
    st.subheader(li.title)
    st.write(f"**{eur(li.price)}** - {li.surface} m2 - {li.rooms} room(s)"
             f" - {li.zone} / {li.quartier or 'quartier unknown'} - "
             f"DPE {li.dpe or '?'} - floor {li.floor}"
             f" - elevator {li.elevator}")
    if li.url:
        st.markdown(f"[Open the listing]({li.url})")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Price vs neighbourhood")
        st.markdown(price_bar_html(a.price), unsafe_allow_html=True)
    with right:
        st.markdown("#### My investment mark")
        show_score(a)
    t1, t2 = st.tabs(["Mortgage", "Rental"])
    with t1:
        show_loan(a, loan_inp)
    with t2:
        show_rental(a)


def manual_listing():
    """Render a form to analyze one listing typed by the user."""
    c = st.columns(3)
    zone = c[0].selectbox("Zone", list(config.ZONES))
    quartier = c[1].selectbox("Quartier", config.ZONES[zone]["quartiers"])
    period = c[2].selectbox("Construction", list(config.PERIOD_FACTOR))
    c = st.columns(4)
    price = c[0].number_input("Price (EUR)", 50_000, 2_000_000, 225_000)
    surface = c[1].number_input("Surface (m2)", 9.0, 200.0, 20.0)
    rooms = c[2].number_input("Rooms", 1, 5, 1)
    dpe = c[3].selectbox("DPE", list("ABCDEFG") + ["?"], index=3)
    c = st.columns(3)
    floor = c[0].number_input("Floor", 0, 30, 2)
    elevator = c[1].checkbox("Elevator", True)
    url = c[2].text_input("Listing URL", "")
    return Listing(title="My listing", price=price, surface=surface,
                   postal_code=config.ZONES[zone]["postal_code"],
                   rooms=int(rooms), zone=zone, quartier=quartier,
                   dpe=None if dpe == "?" else dpe, floor=int(floor),
                   elevator=elevator, construction_period=period, url=url)


def main():
    """Run the Streamlit app."""
    st.title("Paris flat investment agent")
    st.caption("8e - 16e Nord (75116) - 17e Sud (Ternes, Plaine Monceau)")
    source, upload, crit, tol, zones = sidebar_search()
    loan_inp = sidebar_loan()
    rental_inp = sidebar_rental()
    tab_rank, tab_manual = st.tabs(["Ranked listings",
                                    "Analyze one listing"])
    with tab_rank:
        listings = load_listings(source, upload, crit, tol, zones)
        if not listings:
            st.info("No listing found for these criteria.")
        else:
            results = analyze_all(listings, loan_inp, rental_inp)
            df = to_dataframe(results)
            st.dataframe(df[["score", "verdict", "title", "zone",
                             "quartier", "price", "surface", "price_m2",
                             "price_label", "net_yield_pct",
                             "cashflow_after_tax", "url"]],
                         hide_index=True, use_container_width=True)
            st.download_button("Download CSV", df.to_csv(index=False),
                               "ranking.csv")
            labels = [f"{a.score.total}/10 - {a.listing.title}"
                      for a in results]
            pick = st.selectbox("Details of", range(len(results)),
                                format_func=labels.__getitem__)
            show_detail(results[pick], loan_inp)
    with tab_manual:
        listing = manual_listing()
        market.locate(listing)
        show_detail(analyze(listing, loan_inp, rental_inp), loan_inp)


main()
