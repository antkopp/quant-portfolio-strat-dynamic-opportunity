"""
Tests unitaires (hors-ligne, données synthétiques) du pipeline Rotation.

Couvre la LOGIQUE PURE sans accès réseau :
  (a) régime ∈ [-1,1] et bascule sur série synthétique ;
  (b) baromètre monotone vs score de régime (offensif↑ en Risk On, défensif↑ en Risk Off) ;
  (c) allocation : budgets Σ=1, plafonds catégorie/région respectés ;
  (d) sélection : ≤ nmax lignes, Σ poids=1, plafond par position ;
  (e) no-lookahead fondamental : un état filé après as_of est ignoré.
"""

import numpy as np
import pandas as pd
import pytest


# --------------------------------------------------------------------------- (a)
def _synthetic_etf_panel(n=600):
    idx = pd.bdate_range("2018-01-01", periods=n)
    half = n // 2
    up = np.linspace(100, 200, half)
    down = np.linspace(200, 110, n - half)
    spy = np.concatenate([up, down])
    # paniers cycliques/défensifs cohérents avec le marché
    data = {
        "SPY.US": spy,
        "XLK.US": spy * 1.0, "XLY.US": spy * 1.0, "XLI.US": spy,
        "XLB.US": spy, "XLE.US": spy, "XLF.US": spy,
        "XLP.US": np.linspace(100, 130, n), "XLU.US": np.linspace(100, 130, n),
        "XLV.US": np.linspace(100, 130, n),
        "HYG.US": spy * 0.5 + 50, "LQD.US": np.linspace(100, 110, n),
        "IEF.US": np.linspace(100, 105, n), "TLT.US": np.linspace(100, 120, n),
    }
    return pd.DataFrame(data, index=idx)


def test_regime_score_bounds_and_flip():
    from rotation.regime import RulesRegimeEngine, regime_flip_dates
    panel = _synthetic_etf_panel()
    eng = RulesRegimeEngine(params={})
    ser = eng.compute_series(panel)
    assert ser.between(-1, 1).all()
    flips = regime_flip_dates(eng, panel, params={})
    assert len(flips) >= 1                       # uptrend → downtrend ⇒ au moins une bascule
    st = eng.score(panel)
    assert -1 <= st.score <= 1 and st.label in {"risk_on", "risk_off", "neutral"}


# --------------------------------------------------------------------------- (b)
def _meta(symbols_sectors):
    from rotation.config import region_of
    rows = {}
    for sym, sec in symbols_sectors.items():
        rows[sym] = {"sector": sec, "industry": "x", "country": "US",
                     "exchange": sym.rsplit(".", 1)[-1], "region": region_of(sym),
                     "category": f"{sec}|{region_of(sym)}"}
    return pd.DataFrame(rows).T


def _flat_prices(symbols, n=300):
    idx = pd.bdate_range("2019-01-01", periods=n)
    return pd.DataFrame({s: np.linspace(100, 101, n) for s in symbols}, index=idx)


def test_barometer_monotonic_in_regime():
    from rotation.regime import RegimeState
    from rotation.barometer import build_barometer
    meta = _meta({"AAA.US": "Technology", "BBB.US": "Technology", "CCC.US": "Technology",
                  "DDD.US": "Utilities", "EEE.US": "Utilities", "FFF.US": "Utilities"})
    prices = _flat_prices(meta.index)

    on = build_barometer(RegimeState(0.8, "risk_on", prices.index[-1]), prices, meta, {})
    off = build_barometer(RegimeState(-0.8, "risk_off", prices.index[-1]), prices, meta, {})

    tech_on = on.loc["Technology|NA", "tilt"]
    util_on = on.loc["Utilities|NA", "tilt"]
    tech_off = off.loc["Technology|NA", "tilt"]
    util_off = off.loc["Utilities|NA", "tilt"]
    assert tech_on > util_on        # Risk On : offensif > défensif
    assert util_off > tech_off      # Risk Off : défensif > offensif
    assert tech_on > tech_off       # secteur offensif : tilt croît avec le régime


# --------------------------------------------------------------------------- (c)
def test_allocation_caps_and_sum():
    from rotation.allocation import barometer_to_budgets
    bar = pd.DataFrame({
        "sector": ["T", "U", "I", "E"],
        "region": ["NA", "NA", "EU", "EU"],
        "n_names": [5, 5, 5, 5],
        "static_bias": [1, -1, 0.7, 0.6],
        "momentum_z": [1, 0.5, 0.2, 0.1],
        "tilt": [0.9, 0.6, 0.3, 0.1],
        "label": ["offensif"] * 4,
    }, index=["T|NA", "U|NA", "I|EU", "E|EU"])
    params = {"optimizer": {"rotation": {"alloc_top_categories": 8,
                                         "alloc_max_per_category": 0.25,
                                         "alloc_max_per_region": 0.50}}}
    b = barometer_to_budgets(bar, params)
    assert abs(b.sum() - 1.0) < 1e-9
    assert (b <= 0.25 + 1e-9).all()
    region = bar.loc[b.index, "region"]
    assert (b.groupby(region).sum() <= 0.50 + 1e-9).all()


# --------------------------------------------------------------------------- (d)
def test_selection_caps_and_count():
    from rotation.selection import select_positions
    syms = [f"S{i}.US" for i in range(12)] + [f"D{i}.US" for i in range(12)]
    meta = _meta({**{s: "Technology" for s in syms[:12]},
                  **{s: "Utilities" for s in syms[12:]}})
    idx = pd.bdate_range("2019-01-01", periods=200)
    # momentum différencié pour départager les titres
    prices = pd.DataFrame({s: np.linspace(100, 100 + (k % 12), 200)
                           for k, s in enumerate(syms)}, index=idx)
    budgets = pd.Series({"Technology|NA": 0.6, "Utilities|NA": 0.4})
    params = {"optimizer": {"rotation": {"target_positions_min": 10,
                                         "target_positions_max": 20,
                                         "selection_fundamental_weight": 0.0,
                                         "selection_momentum_weight": 1.0,
                                         "max_position_weight": 0.12}}}
    w = select_positions(budgets, meta, prices, None, params)
    assert 0 < len(w) <= 20
    assert abs(w.sum() - 1.0) < 1e-9
    assert (w <= 0.12 + 1e-9).all()


def test_selection_excludes_data_glitch():
    """Garde-fous données : un titre au saut journalier extrême (prix corrompu) est
    EXCLU (sinon le momentum le choisit et sa rampe fait exploser le NAV)."""
    from rotation.selection import select_positions
    syms = [f"G{i}.US" for i in range(6)] + [f"B{i}.US" for i in range(6)]
    meta = _meta({**{s: "Technology" for s in syms[:6]},
                  **{s: "Utilities" for s in syms[6:]}})
    idx = pd.bdate_range("2021-01-01", periods=200)
    data = {s: np.cumprod(1 + np.random.default_rng(k).normal(5e-4, 1e-2, 200)) * 100
            for k, s in enumerate(syms)}
    data["G0.US"] = data["G0.US"].copy()
    data["G0.US"][120:] *= 3.0                  # saut +200% en un jour (glitch)
    prices = pd.DataFrame(data, index=idx)
    budgets = pd.Series({"Technology|NA": 0.5, "Utilities|NA": 0.5})
    rot = {"selection_fundamental_weight": 0.0, "selection_momentum_weight": 1.0,
           "max_position_weight": 0.2, "selection_max_abs_momentum": 4.0,
           "selection_max_daily_jump": 0.6}
    w = select_positions(budgets, meta, prices, None, {"optimizer": {"rotation": rot}})
    assert "G0.US" not in w.index               # exclu par le garde-fou
    # sans les garde-fous, le titre glitché serait sélectionné (momentum le + fort)
    rot_off = {**rot, "selection_max_abs_momentum": 0.0, "selection_max_daily_jump": 0.0}
    w2 = select_positions(budgets, meta, prices, None, {"optimizer": {"rotation": rot_off}})
    assert "G0.US" in w2.index


# --------------------------------------------------------------------------- (e)
class _FakeResp:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class _FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []
        self._rng = None

    def select(self, *a, **k):
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, set(vals))); return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val)); return self

    def lte(self, col, val):
        self.filters.append(("lte", col, val)); return self

    def range(self, a, b):
        self._rng = (a, b); return self

    def execute(self):
        rows = self.rows
        for kind, col, val in self.filters:
            if kind == "in":
                rows = [r for r in rows if r.get(col) in val]
            elif kind == "eq":
                rows = [r for r in rows if r.get(col) == val]
            elif kind == "lte":
                rows = [r for r in rows if str(r.get(col)) <= str(val)]
        if self._rng:
            a, b = self._rng
            rows = rows[a:b + 1]
        return _FakeResp(rows)


class _FakeSchema:
    def __init__(self, tables): self.tables = tables
    def table(self, name): return _FakeQuery(self.tables.get(name, []))


class _FakeClient:
    def __init__(self, tables): self.tables = tables
    def schema(self, name): return _FakeSchema(self.tables)


def test_fundamentals_no_lookahead():
    from rotation.data_fundamentals import FundamentalsPIT
    tickers = [{"id": "id1", "code": "AAA", "exchange": "US"}]
    # schéma déployé : income_statement / balance_sheet en JSONB, period_type, filing_date
    stmts = [
        {"ticker_id": "id1", "period_type": "yearly",
         "fiscal_date": "2020-12-31", "filing_date": "2021-02-15",
         "income_statement": {"totalRevenue": 100, "netIncome": 10},
         "balance_sheet": {"totalStockholderEquity": 50, "totalAssets": 120}},
        {"ticker_id": "id1", "period_type": "yearly",
         "fiscal_date": "2021-12-31", "filing_date": "2022-02-15",   # FUTUR vs as_of
         "income_statement": {"totalRevenue": 200, "netIncome": 30},
         "balance_sheet": {"totalStockholderEquity": 60, "totalAssets": 140}},
    ]
    fake = _FakeClient({"tickers": tickers, "financial_statements": stmts})
    pit = FundamentalsPIT(["US"], _client=fake)

    fetched = pit._fetch_statements(["id1"], "2021-06-30")
    # seul l'état filé le 2021-02-15 est visible ; celui de 2022 est masqué (anti-lookahead)
    assert list(fetched["filing_date"]) == ["2021-02-15"]


# --------------------------------------------------------------------------- (f)
def test_runner_rebalances_on_anchor_and_flip():
    """Rebalancement interne : ancre hebdo (base_rebal_days) + bascule de régime."""
    from rotation.regime import RulesRegimeEngine
    from rotation.runner import RotationContext, build_optimizer_fn

    syms = {}
    for sec in ["Technology", "Utilities", "Industrials", "Consumer Defensive"]:
        for e in ["US", "PA"]:
            for k in range(6):
                syms[f"{sec[:3].upper()}{e}{k}.{e}"] = sec
    meta = _meta(syms)

    # régime : risk_on jusqu'au 2022-03-01, puis bascule risk_off
    ridx = pd.bdate_range("2021-06-01", "2022-06-30")
    score = pd.Series(np.where(ridx < pd.Timestamp("2022-03-01"), 0.6, -0.6), index=ridx)
    ctx = RotationContext(etf_panel=pd.DataFrame(index=ridx), meta=meta,
                          regime_engine=RulesRegimeEngine({}), fundamentals=None,
                          regime_series=score, params={})
    params = {"optimizer": {"rotation": {"selection_fundamental_weight": 0.0,
                                         "selection_momentum_weight": 1.0,
                                         "base_rebal_days": 7}}}
    opt = build_optimizer_fn(params, context=ctx)

    rng = np.random.default_rng(0)
    prices = pd.DataFrame({s: np.cumprod(1 + rng.normal(0.0005, 0.01, 300)) * 100
                           for s in syms}, index=pd.bdate_range("2021-06-01", periods=300))

    rebal_dates, prev = [], None
    for d in pd.bdate_range("2022-02-14", "2022-03-04"):
        sl = prices.loc[:d]
        if sl.empty:
            continue
        w = opt(sl, params)
        key = tuple(sorted(w.index))
        if key != prev:
            rebal_dates.append(d.date())
            prev = key

    # la bascule du 2022-03-01 doit déclencher un rebal (≠ ancre hebdo seule)
    assert pd.Timestamp("2022-03-01").date() in rebal_dates
    # et il doit y avoir au moins une ancre hebdo avant la bascule
    assert sum(1 for d in rebal_dates if d < pd.Timestamp("2022-03-01").date()) >= 1
