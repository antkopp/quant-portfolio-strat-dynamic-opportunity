"""
selection.py — ÉTAPE 4 : analyse des positions individuelles → poids actions finaux.

Dans chaque catégorie dotée d'un budget (étape 3), classe les constituants par un
composite [fondamental PIT (qualité/croissance) + momentum prix], puis sélectionne
les meilleurs pour atteindre 10–20 lignes au total, en répartissant le budget de la
catégorie. Repli sur le momentum seul si aucun fondamental PIT disponible.
"""

import numpy as np
import pandas as pd

from .config import get_param
from .allocation import _waterfill_cap


def _zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=s.index)
    return ((s - s.mean()) / sd).clip(-3, 3)


def _allocate_seats(budget: pd.Series, avail: pd.Series, nmin: int, nmax: int) -> pd.Series:
    """Répartit un nombre total de lignes (∈[nmin,nmax]) entre catégories ∝ budget,
    plancher 1/catégorie, plafonné par le nombre de candidats disponibles."""
    cats = list(budget.index)
    if len(cats) > nmax:                       # trop de catégories : garder les mieux dotées
        cats = budget.sort_values(ascending=False).head(nmax).index.tolist()
        budget = budget[cats] / budget[cats].sum()
    total = min(nmax, max(nmin, len(cats)))
    seats = {c: 1 for c in cats}
    remaining = total - len(cats)
    frac = (budget * total - 1).clip(lower=0).sort_values(ascending=False)
    guard = 0
    while remaining > 0 and guard < 10000:
        progressed = False
        for c in frac.index:
            if remaining <= 0:
                break
            if seats[c] < int(avail.get(c, 0)):
                seats[c] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
        guard += 1
    for c in cats:
        seats[c] = min(seats[c], int(avail.get(c, 0)))
    return pd.Series(seats)


def select_positions(budgets: pd.Series, meta: pd.DataFrame, prices_asof: pd.DataFrame,
                     fund_composite: pd.Series, params: dict) -> pd.Series:
    if budgets is None or budgets.empty:
        return pd.Series(dtype=float)

    lookback = int(get_param(params, "selection_momentum_lookback"))
    w_f = float(get_param(params, "selection_fundamental_weight"))
    w_m = float(get_param(params, "selection_momentum_weight"))
    nmin = int(get_param(params, "target_positions_min"))
    nmax = int(get_param(params, "target_positions_max"))
    maxw = float(get_param(params, "max_position_weight"))

    cats = set(budgets.index)
    cand = meta.index[meta["category"].isin(cats)].intersection(prices_asof.columns)
    if cand.empty:
        return pd.Series(dtype=float)

    # momentum prix sur les candidats
    lb = min(lookback, len(prices_asof) - 1)
    mom = (prices_asof[cand].iloc[-1] / prices_asof[cand].iloc[-1 - lb] - 1.0)
    mom = mom.replace([np.inf, -np.inf], np.nan).dropna()
    cand = mom.index
    mom_z = _zscore(mom)

    # composite : fondamental (déjà z-scoré, PIT) + momentum
    if fund_composite is not None and not fund_composite.empty:
        f = fund_composite.reindex(cand)
        if f.notna().any():
            score = w_f * f.fillna(0.0) + w_m * mom_z
        else:
            score = mom_z
    else:
        score = mom_z

    cat_of = meta.loc[cand, "category"]
    avail = cat_of.value_counts()
    budget = budgets[budgets.index.isin(avail.index)].astype(float)
    if budget.empty:
        return pd.Series(dtype=float)
    budget = budget / budget.sum()

    seats = _allocate_seats(budget, avail, nmin, nmax)

    weights = {}
    for cat, k in seats.items():
        if k <= 0:
            continue
        members = cat_of[cat_of == cat].index
        picks = score.reindex(members).dropna().sort_values(ascending=False).head(int(k)).index
        if len(picks) == 0:
            continue
        per = budget[cat] / len(picks)          # budget de la catégorie réparti également
        for s in picks:
            weights[s] = weights.get(s, 0.0) + per

    if not weights:
        return pd.Series(dtype=float)
    # plafond par position via water-filling (préserve Σ=1 si len·maxw ≥ 1, sinon
    # laisse une part en cash plutôt que de violer le plafond).
    w = pd.Series(weights)
    w = _waterfill_cap(w / w.sum(), maxw)
    return w.sort_values(ascending=False)
