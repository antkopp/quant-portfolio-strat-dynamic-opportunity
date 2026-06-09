"""
data_fundamentals.py — Accès fondamental POINT-IN-TIME (étape 4).

⚠️ Anti-look-ahead : on lit `raw.financial_statements` (qui porte un `filing_date`,
date de publication réelle) et JAMAIS `raw.fundamentals_snapshot` (qui ne contient que
le DERNIER état connu → look-ahead en backtest). À une date `as_of`, seuls les états
dont `filing_date <= as_of` sont visibles.

Composite fondamental (qualité + croissance), calculable uniquement à partir des comptes
(sans prix) → strictement PIT. Les signaux dépendant du prix (valeur, momentum) sont
gérés dans `selection.py` où le panel de prix est disponible.

`fundamentals_snapshot` reste pertinent pour le portefeuille LIVE (voir live_composite).
"""

import json
import logging
import numpy as np
import pandas as pd

from utils.historical_data import get_supabase_client

logger = logging.getLogger(__name__)

# Champs EODHD (camelCase) extraits des JSON `data` par type d'état.
_INCOME_FIELDS  = ["totalRevenue", "netIncome", "ebitda", "grossProfit"]
_BALANCE_FIELDS = ["totalStockholderEquity", "totalAssets"]


def _to_float(x):
    try:
        if x is None or x == "":
            return np.nan
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    mu, sd = s.mean(), s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=s.index)
    return ((s - mu) / sd).clip(-3, 3)


class FundamentalsPIT:
    """Accès fondamental point-in-time. Charge le mapping symbol↔ticker_id une fois,
    puis sert un composite cross-sectionnel z-scoré pour un `as_of` donné.

    Un petit cache mémoire (clé = (as_of, frozenset(symbols))) évite de re-requêter
    la même tranche lors d'un même rebalancement.
    """

    def __init__(self, exchanges, security_types=None, _client=None):
        self.sb = _client or get_supabase_client()
        self._cache = {}
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
        as_of = pd.Timestamp(as_of).strftime("%Y-%m-%d")
        key = (as_of, frozenset(symbols))
        if key in self._cache:
            return self._cache[key]

        ids = [self.sym_to_id[s] for s in symbols if s in self.sym_to_id]
        if not ids:
            return pd.Series(dtype=float)

        raw = self._fetch_statements(ids, as_of)
        metrics = self._compute_metrics(raw)        # DataFrame ticker_id × metric
        if metrics.empty:
            self._cache[key] = pd.Series(dtype=float)
            return self._cache[key]

        # z-score cross-sectionnel par métrique puis moyenne des z disponibles
        zs = metrics.apply(_zscore, axis=0)
        comp = zs.mean(axis=1, skipna=True)
        comp.index = [self.id_to_sym.get(i, i) for i in comp.index]
        comp = comp.dropna()
        self._cache[key] = comp
        return comp

    # ------------------------------------------------------------------
    def _fetch_statements(self, ids, as_of) -> pd.DataFrame:
        """Récupère les états annuels filés <= as_of pour income + balance (batché)."""
        frames = []
        for i in range(0, len(ids), 200):
            chunk = ids[i:i + 200]
            resp = (self.sb.schema("raw").table("financial_statements")
                    .select("ticker_id, statement_type, fiscal_date, filing_date, data")
                    .in_("ticker_id", chunk)
                    .in_("statement_type", ["income_statement", "balance_sheet"])
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
        """ROE, ROA, marge nette, croissance CA/RN à partir des 2 derniers exercices."""
        if raw.empty:
            return pd.DataFrame()
        raw = raw.sort_values("fiscal_date")
        out = {}
        for tid, g in raw.groupby("ticker_id"):
            inc = g[g["statement_type"] == "income_statement"]
            bal = g[g["statement_type"] == "balance_sheet"]
            if inc.empty:
                continue

            def parse(df_, fields):
                vals = []
                for d in df_["data"]:
                    try:
                        j = json.loads(d) if isinstance(d, str) else (d or {})
                    except (json.JSONDecodeError, TypeError):
                        j = {}
                    vals.append({f: _to_float(j.get(f)) for f in fields})
                return pd.DataFrame(vals, index=df_.index)

            inc_v = parse(inc, _INCOME_FIELDS)
            bal_v = parse(bal, _BALANCE_FIELDS)
            last_inc = inc_v.iloc[-1]
            prev_inc = inc_v.iloc[-2] if len(inc_v) >= 2 else None
            last_bal = bal_v.iloc[-1] if not bal_v.empty else pd.Series(dtype=float)

            rev   = last_inc.get("totalRevenue", np.nan)
            ni    = last_inc.get("netIncome", np.nan)
            eq    = last_bal.get("totalStockholderEquity", np.nan)
            assets = last_bal.get("totalAssets", np.nan)

            m = {
                "roe":        ni / eq if eq and eq > 0 else np.nan,
                "roa":        ni / assets if assets and assets > 0 else np.nan,
                "net_margin": ni / rev if rev and rev > 0 else np.nan,
            }
            if prev_inc is not None:
                rev0, ni0 = prev_inc.get("totalRevenue", np.nan), prev_inc.get("netIncome", np.nan)
                m["rev_growth"] = (rev / rev0 - 1) if (rev0 and rev0 > 0) else np.nan
                m["ni_growth"]  = (ni / ni0 - 1) if (ni0 and ni0 > 0) else np.nan
            out[tid] = m
        return pd.DataFrame(out).T
