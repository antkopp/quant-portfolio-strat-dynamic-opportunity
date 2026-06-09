"""
regime.py — ÉTAPE 1 : revue de marché / détection de régime Risk On – Risk Off.

Moteurs PLUGGABLES, sélectionnés via params.optimizer.rotation.regime_method :
  - 'rules'  (défaut) : score composite de signaux market-based sur ETF.
  - 'hmm'             : Gaussian HMM sur rendements/vol des ETF (hmmlearn).
  - 'causal'          : stub (phase 2) — repli sur 'rules' avec avertissement.

Convention de score : continu dans [-1, +1]. +1 = Risk On franc, -1 = Risk Off franc.
État discret dérivé par seuils (on/off/neutral).

Chaque moteur expose :
  - compute_series(panel) -> pd.Series : score de régime quotidien (tout l'historique).
  - score(panel_asof)     -> RegimeState : état/score au dernier point du panel fourni.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import (
    REGIME_ETFS, CYCLICAL_KEYS, DEFENSIVE_KEYS, get_param,
)

logger = logging.getLogger(__name__)


@dataclass
class RegimeState:
    score: float            # [-1, +1]
    label: str              # 'risk_on' | 'risk_off' | 'neutral'
    as_of: pd.Timestamp


# ---------------------------------------------------------------------------
# Helpers de signal
# ---------------------------------------------------------------------------
def _bounded_momentum(s: pd.Series, lookbacks, zwindow: int) -> pd.Series:
    """Momentum multi-horizon → z-score rolling → tanh (borné dans ~[-1,1])."""
    s = s.astype(float)
    parts = []
    for lb in lookbacks:
        mom = s / s.shift(lb) - 1.0
        mu = mom.rolling(zwindow, min_periods=21).mean()
        sd = mom.rolling(zwindow, min_periods=21).std()
        z = (mom - mu) / sd.replace(0, np.nan)
        parts.append(np.tanh(z.fillna(0.0)))
    return pd.concat(parts, axis=1).mean(axis=1)


def _ratio(panel: pd.DataFrame, num_key: str, den_key: str):
    """Série ratio prix de deux ETF (par rôle), ou None si l'un manque."""
    n, d = REGIME_ETFS.get(num_key), REGIME_ETFS.get(den_key)
    if n in panel.columns and d in panel.columns:
        den = panel[d].replace(0, np.nan)
        return panel[n] / den
    return None


def _basket(panel: pd.DataFrame, keys):
    """Panier équipondéré (base 100) des ETF présents parmi `keys`, ou None."""
    syms = [REGIME_ETFS[k] for k in keys if REGIME_ETFS.get(k) in panel.columns]
    if not syms:
        return None
    norm = panel[syms] / panel[syms].iloc[0]
    return norm.mean(axis=1)


# ---------------------------------------------------------------------------
# Moteur : règles composites (défaut)
# ---------------------------------------------------------------------------
class RulesRegimeEngine:
    def __init__(self, params: dict):
        self.params = params or {}
        self.lookbacks = get_param(params, "regime_lookbacks")
        self.zwindow   = get_param(params, "regime_zwindow")
        self.halflife  = get_param(params, "regime_smooth_halflife")
        self.weights   = dict(get_param(params, "regime_weights"))
        self.on_thr    = get_param(params, "regime_on_threshold")
        self.off_thr   = get_param(params, "regime_off_threshold")

    def compute_series(self, panel: pd.DataFrame) -> pd.Series:
        if panel is None or panel.empty:
            return pd.Series(dtype=float)
        lb, zw = self.lookbacks, self.zwindow
        signals = {}  # nom -> série bornée [-1,1]

        broad = REGIME_ETFS.get("broad")
        if broad in panel.columns:
            signals["broad_momentum"] = _bounded_momentum(panel[broad], lb, zw)

        cyc, dfn = _basket(panel, CYCLICAL_KEYS), _basket(panel, DEFENSIVE_KEYS)
        if cyc is not None and dfn is not None:
            signals["cyc_def_ratio"] = _bounded_momentum(cyc / dfn.replace(0, np.nan), lb, zw)

        for name, num, den, sign in [
            ("curve",  "dur_mid",   "dur_long", +1),   # bons courts > longs = taux ↑ = Risk On
            ("credit", "credit_hy", "credit_ig", +1),  # HY > IG = Risk On
            ("em_dm",  "em",        "dm_exus",  +1),    # EM > DM = Risk On
        ]:
            r = _ratio(panel, num, den)
            if r is not None:
                signals[name] = sign * _bounded_momentum(r, lb, zw)

        for name, key, sign in [("gold", "gold", -1), ("usd", "usd", -1)]:
            sym = REGIME_ETFS.get(key)
            if sym in panel.columns:
                signals[name] = sign * _bounded_momentum(panel[sym], lb, zw)

        if not signals:
            logger.warning("Aucun signal de régime calculable (ETF absents).")
            return pd.Series(0.0, index=panel.index)

        # combinaison pondérée sur les signaux DISPONIBLES (poids renormalisés)
        df = pd.DataFrame(signals)
        w = pd.Series({k: self.weights.get(k, 0.0) for k in df.columns})
        w = w / w.sum() if w.sum() > 0 else pd.Series(1.0 / len(df.columns), index=df.columns)
        composite = (df * w).sum(axis=1)
        smoothed = composite.ewm(halflife=self.halflife).mean().clip(-1, 1)
        return smoothed

    def _label(self, score: float) -> str:
        if score >= self.on_thr:
            return "risk_on"
        if score <= self.off_thr:
            return "risk_off"
        return "neutral"

    def score(self, panel_asof: pd.DataFrame) -> RegimeState:
        ser = self.compute_series(panel_asof)
        if ser.empty:
            return RegimeState(0.0, "neutral", pd.Timestamp.now())
        val = float(ser.iloc[-1])
        return RegimeState(val, self._label(val), ser.index[-1])


# ---------------------------------------------------------------------------
# Moteur : Hidden Markov Model
# ---------------------------------------------------------------------------
class HMMRegimeEngine:
    """Gaussian HMM sur (rendement, vol) du marché large + ratio cyc/déf.
    Les états sont mappés sur l'axe Risk On/Off par le rendement moyen latent."""

    def __init__(self, params: dict, n_states: int = 3):
        self.params = params or {}
        self.n_states = int(((params or {}).get("optimizer", {}) or {})
                            .get("rotation", {}).get("regime_hmm_states", n_states))
        self.on_thr  = get_param(params, "regime_on_threshold")
        self.off_thr = get_param(params, "regime_off_threshold")

    def _features(self, panel: pd.DataFrame) -> pd.DataFrame:
        broad = REGIME_ETFS.get("broad")
        if broad not in panel.columns:
            broad = panel.columns[0]
        ret = panel[broad].pct_change()
        vol = ret.rolling(21, min_periods=5).std()
        feats = pd.DataFrame({"ret": ret, "vol": vol})
        cyc, dfn = _basket(panel, CYCLICAL_KEYS), _basket(panel, DEFENSIVE_KEYS)
        if cyc is not None and dfn is not None:
            feats["cycdef"] = (cyc / dfn.replace(0, np.nan)).pct_change()
        return feats.dropna()

    def compute_series(self, panel: pd.DataFrame) -> pd.Series:
        if panel is None or len(panel) < 60:
            return pd.Series(dtype=float)
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            logger.warning("hmmlearn absent → repli sur le moteur 'rules'.")
            return RulesRegimeEngine(self.params).compute_series(panel)

        feats = self._features(panel)
        if len(feats) < 40:
            return pd.Series(0.0, index=panel.index)
        X = feats.values
        model = GaussianHMM(n_components=self.n_states, covariance_type="diag",
                            n_iter=100, random_state=0)
        try:
            model.fit(X)
            states = model.predict(X)
        except Exception as e:
            logger.warning("Échec HMM (%s) → repli 'rules'.", e)
            return RulesRegimeEngine(self.params).compute_series(panel)

        # map état → score : rendement moyen latent, normalisé dans [-1,1]
        mean_ret = model.means_[:, 0]
        order = np.argsort(mean_ret)
        rank = {st: i for i, st in enumerate(order)}
        denom = max(self.n_states - 1, 1)
        state_score = {st: 2 * rank[st] / denom - 1 for st in range(self.n_states)}
        ser = pd.Series([state_score[s] for s in states], index=feats.index)
        return ser.reindex(panel.index).ffill().fillna(0.0)

    def score(self, panel_asof: pd.DataFrame) -> RegimeState:
        ser = self.compute_series(panel_asof)
        if ser.empty:
            return RegimeState(0.0, "neutral", pd.Timestamp.now())
        val = float(ser.iloc[-1])
        label = "risk_on" if val >= self.on_thr else ("risk_off" if val <= self.off_thr else "neutral")
        return RegimeState(val, label, ser.index[-1])


class CausalRegimeEngine(RulesRegimeEngine):
    """Stub (phase 2) : inférence causale régime→secteur. Repli sur 'rules'."""

    def __init__(self, params: dict):
        super().__init__(params)
        logger.warning("regime_method='causal' non implémenté (phase 2) → repli 'rules'.")


# ---------------------------------------------------------------------------
def get_regime_engine(params: dict):
    method = get_param(params, "regime_method")
    if method == "hmm":
        return HMMRegimeEngine(params)
    if method == "causal":
        return CausalRegimeEngine(params)
    return RulesRegimeEngine(params)


def regime_flip_dates(engine, panel: pd.DataFrame, params: dict) -> list:
    """Dates où le LABEL de régime change (pour injection dans extra_rebal_dates :
    rebalancement quotidien déclenché sur bascule de régime)."""
    ser = engine.compute_series(panel)
    if ser.empty:
        return []
    on_thr  = get_param(params, "regime_on_threshold")
    off_thr = get_param(params, "regime_off_threshold")

    def lab(v):
        return "risk_on" if v >= on_thr else ("risk_off" if v <= off_thr else "neutral")

    labels = ser.map(lab)
    flips = labels.ne(labels.shift(1)) & labels.shift(1).notna()
    return [d.strftime("%Y-%m-%d") for d in ser.index[flips]]
