"""
data_fundamentals.py — Accès fondamental POINT-IN-TIME (étape 4).

⚠️ Anti-look-ahead : on lit `raw.financial_statements` (qui porte un `filing_date`,
date de publication réelle) et JAMAIS `raw.fundamentals_snapshot` (qui ne contient que
le DERNIER état connu → look-ahead en backtest). À une date `as_of`, seuls les états
dont `filing_date <= as_of` sont visibles.

Schéma DÉPLOYÉ de raw.financial_statements (1 ligne par ticker × fiscal_date × period_type) :
    ticker_id, fiscal_date, period_type ('yearly'/'quarterly'), filing_date,
    fiscal_year, fiscal_quarter, currency,
    income_statement (JSONB), balance_sheet (JSONB), cash_flow (JSONB)

Composite fondamental (qualité + croissance), calculable uniquement à partir des comptes
(sans prix) → strictement PIT. Les signaux dépendant du prix (valeur, momentum) sont
gérés dans `selection.py`. En cas d'erreur DB (schéma divergent, table absente), le
composant se DÉSACTIVE proprement (→ sélection momentum seul) sans interrompre le backtest.
"""

import json
import logging
import numpy as np
import pandas as pd

from utils.historical_data import get_supabase_client

logger = logging.getLogger(__name__)


def _to_float(x):
    try:
        if x is None or x == "":
            return np.nan
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _as_dict(x):
    """JSONB Supabase → dict (déjà parsé en général ; tolère une chaîne JSON)."""
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    mu, sd = s.mean(), s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=s.index)
    return ((s - mu) / sd).clip(-3, 3)


class FundamentalsPIT:
    """Accès fondamental point-in-time. Charge le mapping symbol↔ticker_id une fois,
    puis sert un composite cross-sectionnel z-scoré pour un `as_of` donné.

    Auto-désactivation (`_disabled`) après une erreur DB → les appels suivants renvoient
    immédiatement vide (la sélection bascule sur le momentum seul)."""

    def __init__(self, exchanges, security_types=None, _client=None):
        self.sb = _client or get_supabase_client()
        self._cache = {}
        self._disabled = False
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
        logger.info("FundamentalsPIT : %d titres mappés", len(self.sym_to_id))

    # ------------------------------------------------------------------
    def composite(self, as_of, symbols) -> pd.Series:
        """Composite fondamental z-scoré (qualité+croissance) pour `symbols` à `as_of`.
        Indexé par symbole ; titres sans état filé <= as_of absents du résultat."""
        if self._disabled:
            return pd.Series(dtype=float)
        as_of = pd.Timestamp(as_of).strftime("%Y-%m-%d")
        key = (as_of, frozenset(symbols))
        if key in self._cache:
            return self._cache[key]

        ids = [self.sym_to_id[s] for s in symbols if s in self.sym_to_id]
        if not ids:
            return pd.Series(dtype=float)

        try:
            raw = self._fetch_statements(ids, as_of)
        except Exception as e:
            logger.warning("Fondamentaux indisponibles (%s) → momentum seul pour la suite.", e)
            self._disabled = True
            return pd.Series(dtype=float)

        metrics = self._compute_metrics(raw)        # DataFrame ticker_id × metric
        if metrics.empty:
            self._cache[key] = pd.Series(dtype=float)
            return self._cache[key]

        zs = metrics.apply(_zscore, axis=0)
        comp = zs.mean(axis=1, skipna=True)
        comp.index = [self.id_to_sym.get(i, i) for i in comp.index]
        comp = comp.dropna()
        self._cache[key] = comp
        return comp

    # ------------------------------------------------------------------
    def _fetch_statements(self, ids, as_of) -> pd.DataFrame:
        """États annuels filés <= as_of (income_statement + balance_sheet JSONB), batché."""
        frames = []
        for i in range(0, len(ids), 200):
            chunk = ids[i:i + 200]
            resp = (self.sb.schema("raw").table("financial_statements")
                    .select("ticker_id, fiscal_date, filing_date, income_statement, balance_sheet")
                    .in_("ticker_id", chunk)
                    .eq("period_type", "yearly")
                    .lte("filing_date", as_of)
                    .execute())
            if resp.data:
                frames.append(pd.DataFrame(resp.data))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _compute_metrics(raw: pd.DataFrame) -> pd.DataFrame:
        """ROE, ROA, marge nette, croissance CA/RN à partir des 2 derniers exercices.
        Chaque ligne porte income_statement ET balance_sheet (JSONB) du même exercice."""
        if raw.empty:
            return pd.DataFrame()
        raw = raw.sort_values("fiscal_date")
        out = {}
        for tid, g in raw.groupby("ticker_id"):
            recs = g.to_dict("records")              # triés par fiscal_date croissant

            def vals(rec):
                inc = _as_dict(rec.get("income_statement"))
                bal = _as_dict(rec.get("balance_sheet"))
                return {
                    "rev":    _to_float(inc.get("totalRevenue")),
                    "ni":     _to_float(inc.get("netIncome")),
                    "eq":     _to_float(bal.get("totalStockholderEquity")),
                    "assets": _to_float(bal.get("totalAssets")),
                }

            last = vals(recs[-1])
            prev = vals(recs[-2]) if len(recs) >= 2 else None
            rev, ni, eq, assets = last["rev"], last["ni"], last["eq"], last["assets"]
            m = {
                "roe":        ni / eq if eq and eq > 0 else np.nan,
                "roa":        ni / assets if assets and assets > 0 else np.nan,
                "net_margin": ni / rev if rev and rev > 0 else np.nan,
            }
            if prev is not None:
                rev0, ni0 = prev["rev"], prev["ni"]
                m["rev_growth"] = (rev / rev0 - 1) if (rev0 and rev0 > 0) else np.nan
                m["ni_growth"]  = (ni / ni0 - 1) if (ni0 and ni0 > 0) else np.nan
            out[tid] = m
        return pd.DataFrame(out).T
