"""
data_factors.py — Facteurs de sélection POINT-IN-TIME (étape 4, multi-facteurs).

`FactorsPIT.factor_frame(as_of, symbols)` → DataFrame indexé par symbole, colonnes =
piliers z-scorés {quality, value, growth, revisions, surprise}, tranchés à `as_of` :

  - fmp_financial_ratios / fmp_key_metrics (`fiscal_date + fmp_report_lag_days ≤ as_of`,
    JSONB `data`) → quality (ROIC, marges) + value (EV/EBITDA, P/B, FCF yield) + growth (YoY RPS) ;
  - fmp_upgrades_downgrades + fmp_price_targets (`published_date ≤ as_of`, fenêtre) → revisions ;
  - earnings_calendar (`report_date ≤ as_of`) → surprise (dernier eps_surprise_pct) ;
    + `earnings_blackout(as_of, days)` → titres publiant sous N jours.

Modèle FundamentalsPIT : map symbol↔ticker_id chargée une fois, requêtes batchées par
ticker_id, **auto-désactivation gracieuse par source** sur erreur DB, cache par as_of.
La couverture FMP est surtout US/développée → les manquants ressortent NaN (repli amont).
"""

import json
import logging

import numpy as np
import pandas as pd

from utils.historical_data import get_supabase_client
from .config import get_param

logger = logging.getLogger(__name__)


def _to_float(x):
    try:
        if x is None or x == "":
            return np.nan
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _as_dict(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _first(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return _to_float(d[k])
    return np.nan


def _zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.nan, index=s.index)
    return ((s - s.mean()) / sd).clip(-3, 3)


# Grades FMP → score numérique (pour upgrades/downgrades).
_GRADE_RANK = {
    "strong sell": 0, "sell": 1, "underperform": 1, "underweight": 1, "reduce": 1,
    "hold": 2, "neutral": 2, "market perform": 2, "equal-weight": 2, "in-line": 2,
    "buy": 3, "outperform": 3, "overweight": 3, "accumulate": 3, "add": 3,
    "strong buy": 4,
}


def _grade(g):
    return _GRADE_RANK.get(str(g or "").strip().lower())


class FactorsPIT:
    def __init__(self, exchanges, security_types=None, _client=None):
        self.sb = _client or get_supabase_client()
        self._cache = {}
        self._off = set()                       # sources désactivées
        security_types = security_types or ["Common Stock"]
        rows, offset, batch = [], 0, 1000
        while True:
            resp = (self.sb.schema("raw").table("tickers")
                    .select("id, code, exchange")
                    .in_("exchange", list(exchanges))
                    .in_("type", list(security_types))
                    .range(offset, offset + batch - 1).execute())
            if not resp.data:
                break
            rows.extend(resp.data)
            if len(resp.data) < batch:
                break
            offset += batch
        self.sym_to_id = {f"{r['code']}.{r['exchange']}": r["id"] for r in rows}
        self.id_to_sym = {v: k for k, v in self.sym_to_id.items()}
        logger.info("FactorsPIT : %d titres mappés", len(self.sym_to_id))

    # ------------------------------------------------------------------
    def factor_frame(self, as_of, symbols) -> pd.DataFrame:
        as_of = pd.Timestamp(as_of)
        key = (as_of.strftime("%Y-%m-%d"), frozenset(symbols))
        if key in self._cache:
            return self._cache[key]
        ids = [self.sym_to_id[s] for s in symbols if s in self.sym_to_id]
        cols = ["quality", "value", "growth", "revisions", "surprise"]
        if not ids:
            out = pd.DataFrame(columns=cols)
            self._cache[key] = out
            return out

        raw_metrics = self._safe("ratios", self._fetch_ratios, ids, as_of)
        q, v, gth = self._pillars_from_ratios(raw_metrics)
        rev = self._safe("revisions", self._fetch_revisions, ids, as_of)
        sur = self._safe("surprise", self._fetch_surprise, ids, as_of)

        df = pd.DataFrame(index=[i for i in ids])
        df["quality"] = pd.Series(q)
        df["value"] = pd.Series(v)
        df["growth"] = pd.Series(gth)
        df["revisions"] = pd.Series(rev)
        df["surprise"] = pd.Series(sur)
        # z-score cross-section par pilier puis index → symboles
        z = df.apply(_zscore, axis=0)
        z.index = [self.id_to_sym.get(i, i) for i in z.index]
        z = z.dropna(how="all")
        self._cache[key] = z
        return z

    def earnings_blackout(self, as_of, symbols, days) -> set:
        """Symboles dont la prochaine publication tombe dans [as_of, as_of+days]."""
        if days <= 0 or "earn_black" in self._off:
            return set()
        as_of = pd.Timestamp(as_of)
        ids = [self.sym_to_id[s] for s in symbols if s in self.sym_to_id]
        if not ids:
            return set()
        hi = (as_of + pd.Timedelta(days=int(days))).strftime("%Y-%m-%d")
        lo = as_of.strftime("%Y-%m-%d")
        blocked = set()
        try:
            for i in range(0, len(ids), 200):
                resp = (self.sb.schema("raw").table("earnings_calendar")
                        .select("ticker_id, report_date")
                        .in_("ticker_id", ids[i:i + 200])
                        .gte("report_date", lo).lte("report_date", hi).execute())
                for r in (resp.data or []):
                    blocked.add(self.id_to_sym.get(r["ticker_id"]))
        except Exception as e:
            logger.warning("earnings_blackout indisponible (%s).", e)
            self._off.add("earn_black")
        return {s for s in blocked if s}

    # ------------------------------------------------------------------
    def _safe(self, name, fn, ids, as_of):
        if name in self._off:
            return {}
        try:
            return fn(ids, as_of)
        except Exception as e:
            logger.warning("FactorsPIT source '%s' indisponible (%s) → ignorée.", name, e)
            self._off.add(name)
            return {}

    def _fetch_ratios(self, ids, as_of):
        """Dernier exercice (+ précédent) par ticker depuis fmp_key_metrics ∪ fmp_financial_ratios."""
        lag = int(get_param({}, "fmp_report_lag_days"))
        cutoff = (as_of - pd.Timedelta(days=lag)).strftime("%Y-%m-%d")
        frames = []
        for table in ("fmp_key_metrics", "fmp_financial_ratios"):
            for i in range(0, len(ids), 200):
                resp = (self.sb.schema("raw").table(table)
                        .select("ticker_id, fiscal_date, data")
                        .in_("ticker_id", ids[i:i + 200])
                        .lte("fiscal_date", cutoff).execute())
                if resp.data:
                    frames.append(pd.DataFrame(resp.data))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _pillars_from_ratios(raw):
        q, v, g = {}, {}, {}
        if raw is None or len(raw) == 0:
            return q, v, g
        raw = raw.sort_values("fiscal_date")
        for tid, grp in raw.groupby("ticker_id"):
            merged = {}
            for d in grp["data"]:
                merged_period = _as_dict(d)
                merged.update({k: val for k, val in merged_period.items() if val not in (None, "")})
            # qualité
            roic = _first(merged, ["roic", "returnOnInvestedCapital", "returnOnTangibleAssets"])
            roe = _first(merged, ["returnOnEquity"])
            margin = _first(merged, ["netProfitMargin", "netIncomePerShare"])
            q_vals = [x for x in (roic, roe, margin) if np.isfinite(x)]
            q[tid] = float(np.mean(q_vals)) if q_vals else np.nan
            # valeur (cheap = élevé) : inverser EV/EBITDA et P/B, garder FCF yield
            ev_ebitda = _first(merged, ["enterpriseValueOverEBITDA", "evToEbitda", "enterpriseValueMultiple"])
            pb = _first(merged, ["pbRatio", "priceToBookRatio", "ptbRatio"])
            fcf_yield = _first(merged, ["freeCashFlowYield", "earningsYield"])
            v_terms = []
            if np.isfinite(ev_ebitda) and ev_ebitda > 0:
                v_terms.append(-np.log(ev_ebitda))
            if np.isfinite(pb) and pb > 0:
                v_terms.append(-np.log(pb))
            if np.isfinite(fcf_yield):
                v_terms.append(fcf_yield)
            v[tid] = float(np.mean(v_terms)) if v_terms else np.nan
            # croissance : YoY revenuePerShare (2 derniers exercices)
            rps = [_first(_as_dict(d), ["revenuePerShare"]) for d in grp["data"]]
            rps = [x for x in rps if np.isfinite(x)]
            g[tid] = (rps[-1] / rps[-2] - 1.0) if len(rps) >= 2 and rps[-2] > 0 else np.nan
        return q, v, g

    def _fetch_revisions(self, ids, as_of):
        win = int(get_param({}, "selection_revisions_window_days"))
        lo = (as_of - pd.Timedelta(days=win)).strftime("%Y-%m-%d")
        hi = as_of.strftime("%Y-%m-%d")
        score = {}
        # upgrades/downgrades : somme des (nouveau grade − ancien grade)
        for i in range(0, len(ids), 200):
            resp = (self.sb.schema("raw").table("fmp_upgrades_downgrades")
                    .select("ticker_id, previous_grade, new_grade, action, published_date")
                    .in_("ticker_id", ids[i:i + 200])
                    .gte("published_date", lo).lte("published_date", hi).execute())
            for r in (resp.data or []):
                ng, pg = _grade(r.get("new_grade")), _grade(r.get("previous_grade"))
                if ng is not None and pg is not None:
                    delta = ng - pg
                elif (r.get("action") or "").lower() in ("upgrade", "up"):
                    delta = 1.0
                elif (r.get("action") or "").lower() in ("downgrade", "down"):
                    delta = -1.0
                else:
                    continue
                tid = r["ticker_id"]
                score[tid] = score.get(tid, 0.0) + delta
        return score

    def _fetch_surprise(self, ids, as_of):
        hi = as_of.strftime("%Y-%m-%d")
        out = {}
        for i in range(0, len(ids), 200):
            resp = (self.sb.schema("raw").table("earnings_calendar")
                    .select("ticker_id, report_date, eps_surprise_pct")
                    .in_("ticker_id", ids[i:i + 200])
                    .lte("report_date", hi)
                    .order("report_date", desc=True).execute())
            for r in (resp.data or []):
                tid = r["ticker_id"]
                if tid not in out:                # 1re ligne = la plus récente (tri desc)
                    sp = _to_float(r.get("eps_surprise_pct"))
                    if np.isfinite(sp):
                        out[tid] = sp
        return out
