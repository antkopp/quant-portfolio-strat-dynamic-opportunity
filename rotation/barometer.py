"""
barometer.py — ÉTAPE 2 : grille baromètre catégorie × {défensif/neutre/offensif}.

Lignes = catégories (secteur GICS × région). Pour chaque catégorie :
  - biais STATIQUE sur l'axe défensif(-1)↔offensif(+1) (config.SECTOR_BIAS),
  - force relative DYNAMIQUE (momentum du panier de la catégorie, z-score cross-section),
  - TILT = combinaison, MODULÉE par le score de régime de l'étape 1 :
        tilt = w_s · (biais_statique × score_régime) + w_m · momentum_z
    → en Risk On (score>0) l'offensif monte ; en Risk Off (score<0) le défensif monte.

Sortie : DataFrame indexé par catégorie, colonnes [sector, region, n_names,
static_bias, momentum_z, tilt, label].
"""

import numpy as np
import pandas as pd

from .config import SECTOR_BIAS, get_param


def _category_momentum(prices_asof: pd.DataFrame, meta: pd.DataFrame,
                       lookback: int) -> pd.Series:
    """Momentum moyen par catégorie (sur les titres présents dans le panel)."""
    if len(prices_asof) <= lookback:
        lookback = max(len(prices_asof) - 1, 1)
    last = prices_asof.iloc[-1]
    past = prices_asof.iloc[-1 - lookback]
    mom = (last / past - 1.0)                      # momentum par titre
    mom = mom.replace([np.inf, -np.inf], np.nan).dropna()

    common = meta.index.intersection(mom.index)
    if common.empty:
        return pd.Series(dtype=float)
    cat = meta.loc[common, "category"]
    return mom.loc[common].groupby(cat).mean()


def build_barometer(regime, prices_asof: pd.DataFrame, meta: pd.DataFrame,
                    params: dict) -> pd.DataFrame:
    lookback = get_param(params, "barometer_momentum_lookback")
    w_s      = get_param(params, "barometer_static_weight")
    w_m      = get_param(params, "barometer_momentum_weight")
    min_names = get_param(params, "barometer_min_names_per_cat")

    # nombre de titres par catégorie (sur l'univers du panel courant)
    present = meta.index.intersection(prices_asof.columns)
    if present.empty:
        return pd.DataFrame(columns=["sector", "region", "n_names",
                                     "static_bias", "momentum_z", "tilt", "label"])
    counts = meta.loc[present, "category"].value_counts()

    cat_mom = _category_momentum(prices_asof, meta, lookback)
    # z-score cross-sectionnel du momentum de catégorie
    if len(cat_mom) > 1 and cat_mom.std(ddof=0) > 0:
        mom_z = (cat_mom - cat_mom.mean()) / cat_mom.std(ddof=0)
    else:
        mom_z = pd.Series(0.0, index=cat_mom.index)
    mom_z = mom_z.clip(-3, 3)

    rows = []
    for cat, n in counts.items():
        if n < min_names:
            continue
        sector, region = (cat.split("|", 1) + ["?"])[:2]
        bias = SECTOR_BIAS.get(sector, 0.0)
        mz = float(mom_z.get(cat, 0.0))
        tilt = w_s * (bias * regime.score) + w_m * mz
        rows.append({
            "category": cat, "sector": sector, "region": region, "n_names": int(n),
            "static_bias": bias, "momentum_z": mz, "tilt": tilt,
            "label": "offensif" if tilt > 0.15 else ("défensif" if tilt < -0.15 else "neutre"),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.set_index("category").sort_values("tilt", ascending=False)
