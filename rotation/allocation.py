"""
allocation.py — ÉTAPE 3 : traduction du baromètre en budgets cibles par catégorie.

Sélectionne les catégories au tilt le plus favorable et leur alloue un budget
proportionnel au tilt, sous contraintes de plafond par catégorie et par région
(diversification). Sortie : pd.Series catégorie → budget, Σ = 1.
"""

import numpy as np
import pandas as pd

from .config import get_param


def _waterfill_cap(w: pd.Series, cap: float) -> pd.Series:
    """Projette w (Σ=1) sous le plafond `cap` par item, en PRÉSERVANT Σ=1 :
    l'excédent des items écrêtés est redistribué aux items sous le plafond
    (proportionnellement), itérativement. Suppose la faisabilité (len·cap ≥ 1)."""
    w = w.astype(float).copy()
    for _ in range(100):
        over = w > cap + 1e-12
        if not over.any():
            break
        excess = float((w[over] - cap).sum())
        w[over] = cap
        under = w < cap - 1e-12
        pool = float(w[under].sum())
        if not under.any() or pool <= 0:
            break
        w[under] += excess * w[under] / pool
    return w


def barometer_to_budgets(barometer: pd.DataFrame, params: dict) -> pd.Series:
    if barometer is None or barometer.empty:
        return pd.Series(dtype=float)

    top_n        = int(get_param(params, "alloc_top_categories"))
    cap_cat      = float(get_param(params, "alloc_max_per_category"))
    cap_region   = float(get_param(params, "alloc_max_per_region"))

    bar = barometer.sort_values("tilt", ascending=False)
    pos = bar[bar["tilt"] > 0]
    chosen = (pos if not pos.empty else bar).head(top_n)
    if chosen.empty:
        return pd.Series(dtype=float)

    # poids bruts ∝ tilt (décalé pour rester positif si tous négatifs)
    tilt = chosen["tilt"].astype(float)
    shifted = tilt - tilt.min() + 1e-6 if (tilt <= 0).any() else tilt
    w = shifted / shifted.sum()

    # Plafonds catégorie + région appliqués conjointement (water-filling, Σ=1 préservé).
    region = chosen["region"]
    for _ in range(50):
        w = _waterfill_cap(w, cap_cat)
        reg_tot = w.groupby(region).sum()
        over = reg_tot[reg_tot > cap_region + 1e-9]
        if over.empty:
            break
        # rabote les régions en excès, redistribue la masse libérée aux régions sous le cap
        freed = float((over - cap_region).sum())
        for r, tot in over.items():
            idx = region[region == r].index
            w.loc[idx] *= cap_region / tot
        under_idx = region[~region.isin(over.index)].index
        pool = float(w[under_idx].sum())
        if len(under_idx) and pool > 0:
            w[under_idx] += freed * w[under_idx] / pool
        else:
            break  # infaisable (ex. une seule région) → on laisse le cap catégorie primer

    return w.sort_values(ascending=False)
