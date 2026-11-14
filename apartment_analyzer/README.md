# Paris flat investment agent

Finds flats for sale in **Paris 8e, 16e Nord (75116) and 17e Sud
(Ternes / Plaine Monceau)** around **200 000 - 250 000 EUR, 19 m2 minimum**,
then for each one:

1. **Price bar** (Google-Flights style): price/m2 vs the quartier average
   (adjusted for small surfaces, blended with the median of the other
   listings found) -> *low / typical / high*.
2. **Mortgage simulation** with your variables: down payment, rate,
   duration, insurance, notary fees, guarantee, works, furniture, debt ratio
   (HCSF 35 %), yearly amortization table.
3. **Rental simulation**: legal max rent (encadrement des loyers, furnished
   or not), taxe fonciere, non-recoverable copro charges, PNO/GLI insurance,
   management, vacancy, maintenance, tax (LMNP reel / micro-BIC,
   micro-foncier / reel), yields and monthly cash-flow.
4. **Investment mark /10** (price 35 %, DPE 20 %, yield 20 %, cash-flow 15 %,
   liquidity 10 %) with pros and cons. DPE G is capped at 4/10 (cannot be
   rented).

## Interactive agent (chat)

Talk to the agent in French or English. It uses Claude with tools to
search listings, change your mortgage / rental variables, analyze, compare
and give its opinion (visit, negotiate - with a target price - or skip).
Your variables persist during the conversation.

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # or: ant auth login
streamlit run apartment_analyzer/app.py    # "Chat with the agent" tab
python -m apartment_analyzer.chat_agent    # same agent in the terminal
```

Example: *"Cherche des studios dans le 17e sud, apport 40k, taux 3,1 % sur
20 ans, meuble, TMI 30 %, puis compare les 3 meilleurs."*

## Run

```bash
pip install -r apartment_analyzer/requirements.txt
streamlit run apartment_analyzer/app.py          # web UI
python -m apartment_analyzer.agent --source bienici --out deals.csv  # CLI
python -m apartment_analyzer.agent --source demo  # fictional demo data
```

## Data sources

* **All portals** (default): Bien'ici + Figaro Immobilier, duplicates of
  the same flat merged (portals listed per flat).
* **Bien'ici (live)**: public but undocumented JSON endpoint aggregating
  most agency listings. It may change or block automated requests.
* **Figaro Immobilier (live)**: public result pages (data embedded in the
  page), fetched slowly with an honest user agent.
* **SeLoger, PAP, LeBonCoin**: they block automated access (captcha /
  bot protection), so the agent does not scrape them. Paste their ads in
  the chat, or put them in a CSV.
* **CSV**: columns `title, price, surface, postal_code` (+ optional
  `rooms, quartier, dpe, floor, elevator, construction_period, url, lat,
  lon, description`) - paste listings from SeLoger, LeBonCoin, PAP...
* **Analyze one listing** tab: type in any listing by hand.

## Caveats

Market prices and rent caps in `config.py` are approximations (2025-26).
Check the official rent cap on referenceloyer.drihl.ile-de-france.gouv.fr
and recent sales on DVF before buying. This is a decision aid, not
financial advice.
