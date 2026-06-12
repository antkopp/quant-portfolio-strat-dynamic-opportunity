"""
config.py — Constantes et paramètres par défaut de la stratégie Rotation.

Tout est surchargeable depuis `params.optimizer.rotation` (params_rotation.yaml).
Les valeurs ici servent de défaut robuste et de documentation des conventions.
"""

# ---------------------------------------------------------------------------
# ÉTAPE 1 — Instruments ETF pour la détection de régime (cotés US, devise USD).
# Symboles au format EODHD `CODE.EXCHANGE`. La couche régime dégrade gracieusement
# si certains manquent en base (voir regime.RulesRegimeEngine).
# ---------------------------------------------------------------------------
REGIME_ETFS = {
    "broad":       "SPY.US",   # marché actions large (momentum directionnel)
    # secteurs cycliques / offensifs
    "cyc_tech":    "XLK.US",
    "cyc_discr":   "XLY.US",
    "cyc_indus":   "XLI.US",
    "cyc_mat":     "XLB.US",
    "cyc_energy":  "XLE.US",
    "cyc_fin":     "XLF.US",
    # secteurs défensifs
    "def_staples": "XLP.US",
    "def_util":    "XLU.US",
    "def_health":  "XLV.US",
    # taux / courbe (duration longue vs intermédiaire)
    "dur_long":    "TLT.US",
    "dur_mid":     "IEF.US",
    # crédit (high yield vs investment grade)
    "credit_hy":   "HYG.US",
    "credit_ig":   "LQD.US",
    # refuges / devise
    "gold":        "GLD.US",
    "usd":         "UUP.US",
    # émergents vs développés ex-US
    "em":          "EEM.US",
    "dm_exus":     "EFA.US",
}

# Paniers cycliques / défensifs pour le ratio Risk On-Risk Off sectoriel.
CYCLICAL_KEYS  = ["cyc_tech", "cyc_discr", "cyc_indus", "cyc_mat", "cyc_energy", "cyc_fin"]
DEFENSIVE_KEYS = ["def_staples", "def_util", "def_health"]

# ---------------------------------------------------------------------------
# ÉTAPE 2 — Taxonomie des catégories du baromètre.
# ---------------------------------------------------------------------------
# Biais statique de chaque secteur sur l'axe défensif(-1) ↔ offensif(+1).
# Clés = valeurs du champ raw.tickers.sector (taxonomie EODHD/Yahoo, 11 secteurs).
SECTOR_BIAS = {
    "Technology":             +1.0,
    "Consumer Cyclical":      +1.0,
    "Industrials":            +0.7,
    "Basic Materials":        +0.7,
    "Energy":                 +0.6,
    "Financial Services":     +0.5,
    "Communication Services": +0.3,
    "Real Estate":            -0.2,
    "Healthcare":             -0.6,
    "Consumer Defensive":     -1.0,
    "Utilities":              -1.0,
}

# Régions agrégées (lignes du baromètre = secteur × région). Mapping par code de
# bourse EODHD (suffixe du symbole `CODE.EXCHANGE`). Inconnu → "Other".
REGION_BY_EXCHANGE = {
    # Amérique du Nord
    "US": "NA", "TO": "NA", "V": "NA", "NE": "NA", "CN": "NA",
    # Europe
    "LSE": "EU", "L": "EU", "IL": "EU", "PA": "EU", "XETRA": "EU", "F": "EU",
    "SW": "EU", "VX": "EU", "AS": "EU", "BR": "EU", "MC": "EU", "MI": "EU",
    "VI": "EU", "HE": "EU", "CO": "EU", "ST": "EU", "OL": "EU", "IC": "EU",
    "LS": "EU", "IR": "EU", "AT": "EU", "BE": "EU",
    # Asie / Océanie développée
    "T": "ADM", "TSE": "ADM", "HK": "ADM", "KO": "ADM", "KS": "ADM", "KQ": "ADM",
    "SI": "ADM", "AU": "ADM", "AX": "ADM", "NZ": "ADM",
    # Émergents
    "SS": "EM", "SZ": "EM", "NS": "EM", "BO": "EM", "SA": "EM", "MX": "EM",
    "JO": "EM", "TA": "EM", "TW": "EM", "BK": "EM",
}

# Bourses ACWI par défaut (codes EODHD). Tunable depuis params.universe.exchanges.
ACWI_EXCHANGES = [
    "US", "TO",                              # NA
    "LSE", "PA", "XETRA", "SW", "AS", "MC", "MI", "BR", "VI", "HE", "CO", "ST", "OL", "IR", "LS",  # EU
    "T", "HK", "KO", "SI", "AU",             # ADM
    "SS", "NS", "SA", "MX", "JO", "TA", "TW",  # EM
]

# ---------------------------------------------------------------------------
# Paramètres de scoring (surchargeables).
# ---------------------------------------------------------------------------
DEFAULTS = {
    # --- régime ---
    "regime_method": "rules",          # 'rules' | 'hmm' | 'causal'
    "regime_lookbacks": [21, 63, 126], # momentum multi-horizon (jours ouvrés)
    "regime_zwindow": 252,             # fenêtre de z-score des sous-signaux
    "regime_smooth_halflife": 5,       # lissage EWM du score composite (jours)
    "regime_on_threshold": 0.20,       # score > seuil → Risk On
    "regime_off_threshold": -0.20,     # score < -seuil → Risk Off

    # --- rebalancement hybride (décision interne, cadence moteur = quotidienne) ---
    "base_rebal_days": 7,              # ancre calendaire (jours) — 7 = hebdo

    # pondération des sous-signaux du régime 'rules' (somme normalisée en interne)
    "regime_weights": {
        "broad_momentum": 1.0,
        "cyc_def_ratio":  1.0,
        "curve":          0.6,   # pente (duration courte surperforme = Risk On)
        "credit":         0.8,   # HY vs IG (HY surperforme = Risk On)
        "gold":           0.4,   # or fort = Risk Off
        "usd":            0.4,   # USD fort = Risk Off
        "em_dm":          0.5,   # EM surperforme DM = Risk On
    },

    # --- baromètre ---
    "barometer_momentum_lookback": 126,  # force relative des catégories (jours)
    "barometer_static_weight": 0.5,      # poids du biais statique × régime
    "barometer_momentum_weight": 0.5,    # poids de la force relative dynamique
    "barometer_min_names_per_cat": 3,    # catégorie ignorée si trop peu de titres

    # --- allocation (étape 3) ---
    "alloc_top_categories": 8,    # nb de catégories retenues (tilt positif)
    "alloc_max_per_category": 0.25,
    "alloc_max_per_region": 0.50,

    # --- sélection (étape 4) ---
    "target_positions_min": 10,
    "target_positions_max": 20,
    "selection_fundamental_weight": 0.5,
    "selection_momentum_weight": 0.5,
    "selection_momentum_lookback": 126,
    "max_position_weight": 0.12,
    "min_adtv_rank_pct": 0.0,     # filtre liquidité optionnel (0 = désactivé)
    # garde-fou données : exclut les candidats au |momentum| > seuil sur la fenêtre
    # (prix ×N = split/devise non ajusté → ferait exploser le NAV). 0 = désactivé.
    "selection_max_abs_momentum": 4.0,   # 400 % sur ~6 mois
    # garde-fou données : exclut les candidats ayant un saut JOURNALIER > seuil sur la
    # fenêtre (print aberrant / split non ajusté). 0 = désactivé.
    "selection_max_daily_jump": 0.6,     # 60 % en un jour

    # --- intégration macro (étapes 1-2) ---
    "regime_macro_weight": 0.40,         # poids du score macro vs market-based (régime 1D)
    "barometer_macro_weight": 0.50,      # poids des tilts macro (secteur+région) dans le baromètre
    "macro_surprise_window_days": 120,   # fenêtre d'agrégation des surprises (economic_events)
    "macro_pub_lag_days": 90,            # retard de publication macro_indicators (PIT)
    "gmd_pub_lag_days": 365,             # retard de publication global_macro_data (PIT)
    "regime_method_2d": False,           # True → régime quadrant croissance×inflation (Phase 2)

    # --- sélection multi-facteurs (étape 4, Phase 3) ---
    "fmp_report_lag_days": 75,           # retard de publication fmp_ratios/key_metrics (PIT)
    "selection_revisions_window_days": 120,
    "earnings_blackout_days": 0,         # exclut les titres publiant sous N jours (0 = off)
    "selection_factor_weights": {        # poids des piliers (renormalisés sur les dispos)
        "quality":   1.0,
        "value":     0.8,
        "growth":    0.8,
        "revisions": 1.0,
        "surprise":  0.6,
        "momentum":  1.0,
    },
}


def get_param(params: dict, key: str):
    """Lit un paramètre rotation depuis params.optimizer.rotation, sinon DEFAULTS."""
    rot = ((params or {}).get("optimizer", {}) or {}).get("rotation", {}) or {}
    if key in rot:
        return rot[key]
    return DEFAULTS[key]


def region_of(symbol: str) -> str:
    """Région agrégée d'un symbole d'après son suffixe de bourse."""
    if not isinstance(symbol, str) or "." not in symbol:
        return "NA"  # convention Yahoo (sans suffixe) = US
    suffix = symbol.rsplit(".", 1)[-1].upper()
    return REGION_BY_EXCHANGE.get(suffix, "Other")


# ---------------------------------------------------------------------------
# MACRO — cartes pays → région (grandes économies, suffisant pour l'agrégation).
# `country_iso3` pour macro_indicators / global_macro_data ; codes EODHD (2 lettres)
# pour economic_events.
# ---------------------------------------------------------------------------
REGION_BY_ISO3 = {
    "USA": "NA", "CAN": "NA",
    "DEU": "EU", "FRA": "EU", "GBR": "EU", "CHE": "EU", "ITA": "EU", "ESP": "EU",
    "NLD": "EU", "SWE": "EU", "BEL": "EU", "AUT": "EU", "NOR": "EU", "DNK": "EU", "FIN": "EU",
    "JPN": "ADM", "AUS": "ADM", "HKG": "ADM", "SGP": "ADM", "KOR": "ADM", "NZL": "ADM",
    "CHN": "EM", "IND": "EM", "BRA": "EM", "MEX": "EM", "ZAF": "EM", "TWN": "EM", "TUR": "EM",
}
REGION_BY_COUNTRY_CODE = {   # codes EODHD economic_events (≈ ISO2)
    "US": "NA", "CA": "NA",
    "DE": "EU", "FR": "EU", "GB": "EU", "UK": "EU", "CH": "EU", "IT": "EU", "ES": "EU",
    "NL": "EU", "SE": "EU",
    "JP": "ADM", "AU": "ADM", "HK": "ADM", "SG": "ADM", "KR": "ADM",
    "CN": "EM", "IN": "EM", "BR": "EM", "MX": "EM", "ZA": "EM",
}
REGIONS = ["NA", "EU", "ADM", "EM"]


def region_of_country(code: str) -> str:
    """Région d'un code pays (ISO3 ou code EODHD 2 lettres), sinon 'Other'."""
    if not code:
        return "Other"
    c = str(code).upper()
    return REGION_BY_ISO3.get(c) or REGION_BY_COUNTRY_CODE.get(c, "Other")


# Indicateurs macro_indicators par thème (indicator_code EODHD).
MACRO_INDICATORS = {
    "growth":     ["gdp_growth_annual", "gdp_current_usd"],
    "inflation":  ["inflation_consumer_prices_annual"],
    "real_rate":  ["real_interest_rate"],
    "unemployment": ["unemployment_total_percent"],
}

# Classification des economic_events par mots-clés du champ event_type (libellé EODHD).
EVENT_CATEGORY_KEYWORDS = {
    "growth":    ["gdp", "pmi", "ism", "industrial production", "retail sales",
                  "employment", "payroll", "nonfarm", "unemployment", "confidence"],
    "inflation": ["cpi", "inflation", "ppi", "price index", "pce"],
    "policy":    ["interest rate", "rate decision", "fed", "ecb", "boj", "policy rate"],
}

# Sensibilité macro→secteur : signe de l'effet d'une HAUSSE de chaque variable macro sur
# l'attrait relatif du secteur. Clés = secteurs raw (taxonomie EODHD/Yahoo).
# Variables : growth (surprise/tendance de croissance), inflation, real_rate (taux réel).
MACRO_SECTOR_SENSITIVITY = {
    #                         growth  inflation  real_rate
    "Technology":            (+1.0,    -0.3,     -0.6),
    "Consumer Cyclical":     (+1.0,    -0.3,     -0.4),
    "Industrials":           (+0.8,    +0.1,     -0.2),
    "Basic Materials":       (+0.6,    +0.8,     -0.1),
    "Energy":                (+0.4,    +1.0,     +0.1),
    "Financial Services":    (+0.5,    +0.1,     +0.8),
    "Communication Services": (+0.4,   -0.2,     -0.3),
    "Real Estate":           (+0.2,    +0.3,     -0.8),
    "Healthcare":            (-0.2,    -0.1,     -0.1),
    "Consumer Defensive":    (-0.4,    +0.2,     +0.0),
    "Utilities":             (-0.5,    +0.1,     -0.7),
}

# Phase 2 — playbook quadrant croissance×inflation → biais sectoriel.
# Quadrants : 'goldilocks' (croissance+, inflation−), 'reflation' (+,+),
#             'stagflation' (−,+), 'deflation' (−,−).
QUADRANT_PLAYBOOK = {
    "goldilocks":  {"Technology": 1.0, "Consumer Cyclical": 1.0, "Communication Services": 0.6,
                    "Industrials": 0.5, "Utilities": -0.6, "Consumer Defensive": -0.6},
    "reflation":   {"Energy": 1.0, "Basic Materials": 1.0, "Financial Services": 0.8,
                    "Industrials": 0.6, "Utilities": -0.4, "Technology": -0.2},
    "stagflation": {"Energy": 1.0, "Consumer Defensive": 0.6, "Healthcare": 0.5,
                    "Utilities": 0.3, "Consumer Cyclical": -0.8, "Technology": -0.6},
    "deflation":   {"Consumer Defensive": 1.0, "Utilities": 0.8, "Healthcare": 0.8,
                    "Technology": -0.2, "Energy": -0.8, "Basic Materials": -0.8},
}
