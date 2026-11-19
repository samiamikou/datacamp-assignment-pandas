"""Madrid reference data: target barrios, prices, market rents, costs.

APPROXIMATIONS for late 2025 / 2026 (asking prices and rents of the
main portals, by barrio). Check recent sales (Notariado / Registradores
statistics) and comparable rents before making an offer.

Madrid has NO legal rent cap: the Comunidad de Madrid did not declare
"zonas tensionadas" under the 2023 housing law, so rents are free and
the model uses an estimated market rent.
"""

SEARCH = {
    "min_price": 200_000,
    "max_price": 250_000,
    "min_surface": 19.0,
    "exclude_ground_floor": True,  # no "bajo" / "semisotano"
}
MIN_PLAUSIBLE_PRICE_M2 = 4_000

# District -> barrios kept. Elegant, classic and calm, priced below the
# prime barrios next door (Almagro, Recoletos, Castellana, Jeronimos,
# El Viso).
ZONES = {
    "Chamberí": ["Trafalgar", "Arapiles", "Gaztambide", "Vallehermoso",
                 "Ríos Rosas"],
    "Salamanca": ["Guindalera", "Fuente del Berro"],
    "Retiro": ["Niño Jesús", "Pacífico", "Adelfas"],
    "Chamartín": ["Prosperidad", "Hispanoamérica"],
}
POSTAL_CODES = {
    "Chamberí": ["28010", "28015", "28003"],
    "Salamanca": ["28028", "28009"],
    "Retiro": ["28007", "28009"],
    "Chamartín": ["28002", "28016"],
}

# Asking price, EUR per m2.
MARKET_PRICE_M2 = {
    "Trafalgar": 8_400, "Arapiles": 8_300, "Gaztambide": 8_000,
    "Vallehermoso": 8_100, "Ríos Rosas": 8_200,
    "Guindalera": 7_500, "Fuente del Berro": 7_700,
    "Niño Jesús": 7_600, "Pacífico": 6_400, "Adelfas": 6_200,
    "Prosperidad": 7_100, "Hispanoamérica": 7_300,
}
ZONE_PRICE_M2 = {"Chamberí": 8_200, "Salamanca": 7_600, "Retiro": 6_800,
                 "Chamartín": 7_200}

# Long-term market rent, EUR per m2 per month (small flats rent higher
# per m2: see SMALL_SURFACE_RENT).
RENT_M2 = {
    "Trafalgar": 25.5, "Arapiles": 25.0, "Gaztambide": 24.5,
    "Vallehermoso": 24.5, "Ríos Rosas": 24.5,
    "Guindalera": 23.5, "Fuente del Berro": 23.5,
    "Niño Jesús": 23.0, "Pacífico": 21.5, "Adelfas": 21.0,
    "Prosperidad": 22.0, "Hispanoamérica": 22.5,
}
ZONE_RENT_M2 = {"Chamberí": 25.0, "Salamanca": 23.5, "Retiro": 22.0,
                "Chamartín": 22.0}
SMALL_SURFACE_PREMIUM = [(30, 1.08), (40, 1.04)]
SMALL_SURFACE_RENT = [(30, 1.12), (40, 1.05)]
SEASONAL_RENT_FACTOR = 1.15   # "alquiler de temporada" (1-11 months)

# Running costs, EUR per m2 per year (landlord pays IBI and comunidad).
IBI_M2 = 6.0
COMUNIDAD_M2 = 28.0
WASTE_TAX = 90.0              # tasa de residuos (Madrid)

# Energy certificate: no rental ban in Spain, so a softer score.
ENERGY_RULES = {
    "A": (10, "Excellent energy rating."),
    "B": (10, "Very good energy rating."),
    "C": (9, "Good energy rating."),
    "D": (8, "Average energy rating."),
    "E": (6, "Mediocre energy rating: higher bills for tenants."),
    "F": (4, "Poor energy rating: plan insulation or windows."),
    "G": (3, "Very poor energy rating: works recommended."),
}
