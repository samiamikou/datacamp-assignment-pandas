"""Reference data: target zones, market prices and rent-control values.

All figures are APPROXIMATIONS (late 2025 / 2026) compiled from public
sources (Notaires du Grand Paris / DVF price levels, DRIHL rent-control
grid of 1 July 2025). They are editable defaults: check them against
https://www.referenceloyer.drihl.ile-de-france.gouv.fr and recent DVF
sales before making a decision.
"""

# Search criteria requested by the user.
SEARCH = {
    "min_price": 200_000,
    "max_price": 250_000,
    "min_surface": 19.0,
}

# Target zones -> postal code + administrative "quartiers" kept.
ZONES = {
    "8e": {
        "postal_code": "75008",
        "quartiers": ["Champs-Elysees", "Faubourg-du-Roule",
                      "Madeleine", "Europe"],
    },
    "16e Nord": {
        "postal_code": "75116",
        "quartiers": ["Chaillot", "Porte-Dauphine", "Muette Nord"],
    },
    "17e Sud": {
        "postal_code": "75017",
        "quartiers": ["Ternes", "Plaine-de-Monceaux"],
    },
}

# Average resale price (ancien) in EUR per m2, per quartier.
MARKET_PRICE_M2 = {
    "Champs-Elysees": 12_200,
    "Faubourg-du-Roule": 11_300,
    "Madeleine": 11_800,
    "Europe": 10_600,
    "Chaillot": 12_000,
    "Porte-Dauphine": 11_200,
    "Muette Nord": 10_900,
    "Ternes": 10_900,
    "Plaine-de-Monceaux": 10_700,
}

# Fallback when only the zone is known.
ZONE_PRICE_M2 = {"8e": 11_300, "16e Nord": 11_400, "17e Sud": 10_800}

# Small flats sell at a premium per m2. (max surface, multiplier).
SMALL_SURFACE_PREMIUM = [(20, 1.10), (25, 1.07), (30, 1.04)]

# Rent control: "loyer de reference majore" (legal ceiling, EUR/m2/month)
# for an UNFURNISHED 1-room flat built before 1946.
RENT_CAP_M2_BASE = {
    "Champs-Elysees": 41.0,
    "Faubourg-du-Roule": 40.3,
    "Madeleine": 40.3,
    "Europe": 40.3,
    "Chaillot": 40.3,
    "Porte-Dauphine": 39.6,
    "Muette Nord": 39.6,
    "Ternes": 39.6,
    "Plaine-de-Monceaux": 39.6,
}
ZONE_RENT_CAP_M2 = {"8e": 40.3, "16e Nord": 39.8, "17e Sud": 39.6}

# Adjustments applied to the base cap.
FURNISHED_FACTOR = 1.135
ROOMS_FACTOR = {1: 1.0, 2: 0.88, 3: 0.84}
PERIOD_FACTOR = {
    "avant 1946": 1.0,
    "1946-1970": 0.93,
    "1971-1990": 0.88,
    "apres 1990": 0.97,
}

# Default yearly running costs (EUR per m2 per year).
TAXE_FONCIERE_M2 = 28.0
COPRO_CHARGES_M2 = 45.0
NON_RECOVERABLE_SHARE = 0.35

# Energy label: score /10 and regulatory comment.
DPE_RULES = {
    "A": (10, "Excellent energy label."),
    "B": (10, "Very good energy label."),
    "C": (9, "Good energy label."),
    "D": (7, "Average label, rentable without limit."),
    "E": (5, "Rental ban from 2034: plan works."),
    "F": (2, "Rental ban from 2028, rent frozen: works needed."),
    "G": (0, "Rental already banned since 2025."),
}
