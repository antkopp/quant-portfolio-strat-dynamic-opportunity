"""
runner.py — Orchestrateur de la stratégie « Dynamic Opportunity » (Rotation Risk On-Risk Off).

Assemble le pipeline 4 étapes en un `optimizer_fn(prices, params)` compatible avec le
moteur de backtest de la base (`run_portfolio_backtest`), exactement comme
`gcmp_runner.build_optimizer_fn` dans les autres stratégies.

REBALANCEMENT HYBRIDE (hebdo + quotidien), sans modifier la base :
le moteur appelle l'optimiseur à CADENCE QUOTIDIENNE (rebalance_frequency='B') ; un
CACHE D'ÉTAT décide s'il faut réellement rebalancer :
  - ancre calendaire (tous les `base_rebal_days` jours, défaut 7 = hebdo), OU
  - BASCULE DE RÉGIME Risk On↔Off détectée ce jour-là (déclenchement événementiel quotidien).
Sinon l'optimiseur renvoie les poids cachés (le moteur gère le drift entre deux rebal).

Anti-look-ahead : `as_of = prices.index[-1]` à chaque appel. Le score de régime est lu
sur une série pré-calculée par le moteur de régime ; pour `regime_method='rules'` cette
série est strictement causale (rolling/EWM) donc PIT-safe. Pour `hmm`/`causal`, le fit
plein-échantillon introduit un léger look-ahead sur le TIMING des bascules → préférer la
cadence hebdo pure pour ces méthodes (production : refit par rebalancement, cf. TODO).
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

from .config import get_param
from .data_etf import load_regime_etf_panel
from .data_meta import load_stock_metadata
from .regime import get_regime_engine, RegimeState
from .barometer import build_barometer
from .allocation import barometer_to_budgets
from .selection import select_positions

logger = logging.getLogger(__name__)


def _label(score: float, on_thr: float, off_thr: float) -> str:
    if score >= on_thr:
        return "risk_on"
    if score <= off_thr:
        return "risk_off"
    return "neutral"


class RotationContext:
    def __init__(self, etf_panel, meta, regime_engine, fundamentals, regime_series, params):
        self.etf_panel = etf_panel
        self.meta = meta
        self.regime_engine = regime_engine
        self.fundamentals = fundamentals
        self.regime_series = regime_series
        self.params = params

    @classmethod
    def build(cls, params: dict):
        bt = params.get("backtest", {}) or {}
        uni = params.get("universe", {}) or {}
        source = params.get("source", "auto")
        start_date = bt.get("start_date_data") or "2005-01-04"
        end_date = bt.get("end_date") or pd.Timestamp.today().strftime("%Y-%m-%d")
        exchanges = uni.get("exchanges", ["US"])
        include_delisted = uni.get("include_delisted", True)
        security_types = uni.get("security_types", ["Common Stock"])

        logger.info("RotationContext : chargement panel ETF de régime…")
        etf_panel = load_regime_etf_panel(start_date, end_date, source=source)

        logger.info("RotationContext : chargement métadonnées titres…")
        meta = load_stock_metadata(exchanges, include_delisted, security_types)

        regime_engine = get_regime_engine(params)
        logger.info("RotationContext : pré-calcul de la série de régime…")
        regime_series = regime_engine.compute_series(etf_panel)

        fundamentals = None
        if get_param(params, "selection_fundamental_weight") > 0:
            try:
                from .data_fundamentals import FundamentalsPIT
                fundamentals = FundamentalsPIT(exchanges, security_types)
            except Exception as e:
                logger.warning("FundamentalsPIT indisponible (%s) → sélection momentum seul.", e)

        return cls(etf_panel, meta, regime_engine, fundamentals, regime_series, params)


def build_optimizer_fn(params: dict, context: "RotationContext" = None):
    """Construit l'optimizer_fn de la stratégie (closure à état pour le rebalancement).

    `context` injectable (tests) ; sinon construit via RotationContext.build(params)."""
    ctx = context if context is not None else RotationContext.build(params)

    on_thr = float(get_param(params, "regime_on_threshold"))
    off_thr = float(get_param(params, "regime_off_threshold"))
    base_days = int(get_param(params, "base_rebal_days"))
    use_fund = get_param(params, "selection_fundamental_weight") > 0 and ctx.fundamentals is not None

    state = {"weights": pd.Series(dtype=float), "last_rebal": None, "last_label": None}

    def optimizer_fn(prices: pd.DataFrame, loaded_params: dict) -> pd.Series:
        if prices is None or prices.empty:
            return state["weights"]
        as_of = prices.index[-1]

        # --- ÉTAPE 1 — régime au point as_of ---
        if ctx.regime_series is not None and not ctx.regime_series.empty:
            val = ctx.regime_series.asof(as_of)
            score = 0.0 if pd.isna(val) else float(val)
        else:
            score = 0.0
        label = _label(score, on_thr, off_thr)

        flip = state["last_label"] is not None and label != state["last_label"]
        due = (state["last_rebal"] is None or state["weights"].empty
               or (as_of - state["last_rebal"]).days >= base_days or flip)
        state["last_label"] = label
        if not due:
            return state["weights"]

        regime = RegimeState(score, label, as_of)

        # --- ÉTAPE 2 — baromètre ---
        barometer = build_barometer(regime, prices, ctx.meta, loaded_params)
        if barometer.empty:
            return state["weights"]

        # --- ÉTAPE 3 — budgets par catégorie ---
        budgets = barometer_to_budgets(barometer, loaded_params)
        if budgets.empty:
            return state["weights"]

        # --- ÉTAPE 4 — sélection fondamentale PIT + momentum ---
        fund = None
        if use_fund:
            cats = set(budgets.index)
            cand = ctx.meta.index[ctx.meta["category"].isin(cats)].intersection(prices.columns)
            if len(cand):
                fund = ctx.fundamentals.composite(as_of, list(cand))

        weights = select_positions(budgets, ctx.meta, prices, fund, loaded_params)
        if weights.empty:
            return state["weights"]

        reason = "flip" if flip else ("init" if state["last_rebal"] is None else "hebdo")
        logger.info("[%s] rebal (%s) régime=%s score=%+.2f → %d lignes",
                    pd.Timestamp(as_of).date(), reason, label, score, len(weights))
        state["weights"] = weights
        state["last_rebal"] = as_of
        return weights

    return optimizer_fn
