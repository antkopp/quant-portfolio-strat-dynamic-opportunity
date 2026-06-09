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
