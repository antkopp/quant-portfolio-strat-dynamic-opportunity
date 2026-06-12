"""
data_macro.py — Accès macro POINT-IN-TIME (étapes 1-2).

`MacroPIT.features(as_of)` renvoie des features macro **globales et par région**
{NA, EU, ADM, EM}, toutes tranchées à `as_of` (aucun look-ahead) :

  - surprises économiques (raw.economic_events, `event_date ≤ as_of`, fenêtre glissante) :
    growth_surprise, inflation_surprise  ∈ [-1, +1]   (moyenne de signes actual−estimate,
    chômage inversé) ;
  - niveaux/tendances (raw.macro_indicators, `period_date + macro_pub_lag_days ≤ as_of`) :
    growth, growth_trend, inflation, real_rate.

Modèle calqué sur FundamentalsPIT : requêtes batchées, **auto-désactivation gracieuse**
par source en cas d'erreur DB (→ feature = 0, le backtest continue), cache par `as_of`.

⚠️ La sync economic_events ne couvre qu'une fenêtre glissante courte → l'historique peut
être faible ; dans ce cas growth/inflation_surprise valent 0 et seul macro_indicators porte
le signal. `check_coverage` mesure cette profondeur.
"""

import logging
import re

import numpy as np
import pandas as pd

from utils.historical_data import get_supabase_client
from .config import (
    region_of_country, REGIONS, MACRO_INDICATORS, EVENT_CATEGORY_KEYWORDS, get_param,
)

logger = logging.getLogger(__name__)

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")
_MULT = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _parse_num(x):
    """Parse un nombre macro ('3.2%', '150K', '1.5M', '(2.1)' négatif) → float ou NaN."""
    if x is None:
        return np.nan
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return np.nan
    neg = s.startswith("(") and s.endswith(")")
    m = _NUM_RE.search(s.replace(",", ""))
    if not m:
        return np.nan
    val = float(m.group())
    for suf, mult in _MULT.items():
        if suf in s.upper():
            val *= mult
            break
    return -val if neg else val


def _classify_event(event_type: str) -> str:
    t = (event_type or "").lower()
    for cat, kws in EVENT_CATEGORY_KEYWORDS.items():
        if any(k in t for k in kws):
            return cat
    return "other"


def _empty_region_map():
    return {r: 0.0 for r in (["global"] + REGIONS)}


class MacroPIT:
    def __init__(self, _client=None):
        self.sb = _client or get_supabase_client()
        self._cache = {}
        self._events_off = False
        self._indic_off = False

    # ------------------------------------------------------------------
    def features(self, as_of) -> dict:
        as_of = pd.Timestamp(as_of)
        key = as_of.strftime("%Y-%m-%d")
        if key in self._cache:
            return self._cache[key]
        feats = {
            "growth_surprise":    _empty_region_map(),
            "inflation_surprise": _empty_region_map(),
            "growth":             _empty_region_map(),
            "growth_trend":       _empty_region_map(),
            "inflation":          _empty_region_map(),
            "real_rate":          _empty_region_map(),
        }
        try:
            self._fill_surprises(as_of, feats)
        except Exception as e:
            logger.warning("MacroPIT economic_events indisponible (%s) → surprises = 0.", e)
            self._events_off = True
        try:
            self._fill_levels(as_of, feats)
        except Exception as e:
            logger.warning("MacroPIT macro_indicators indisponible (%s) → niveaux = 0.", e)
            self._indic_off = True
        self._cache[key] = feats
        return feats

    # ------------------------------------------------------------------
    def _fill_surprises(self, as_of, feats):
        if self._events_off:
            return
        window = int(get_param({}, "macro_surprise_window_days"))
        lo = (as_of - pd.Timedelta(days=window)).strftime("%Y-%m-%d")
        hi = as_of.strftime("%Y-%m-%d")
        resp = (self.sb.schema("raw").table("economic_events")
                .select("country, event_type, actual, estimate, event_date")
                .gte("event_date", lo).lte("event_date", hi).execute())
        rows = resp.data or []
        if not rows:
            return
        # contributions par (région, catégorie)
        buckets = {(r, c): [] for r in (["global"] + REGIONS)
                   for c in ("growth", "inflation")}
        for r in rows:
            cat = _classify_event(r.get("event_type"))
            if cat not in ("growth", "inflation"):
                continue
            a, e = _parse_num(r.get("actual")), _parse_num(r.get("estimate"))
            if not (np.isfinite(a) and np.isfinite(e)):
                continue
            sign = float(np.sign(a - e))
            if cat == "growth" and "unemploy" in (r.get("event_type") or "").lower():
                sign = -sign                      # chômage ↑ = croissance ↓
            region = region_of_country(r.get("country"))
            buckets[("global", cat)].append(sign)
            if region in REGIONS:
                buckets[(region, cat)].append(sign)
        for (region, cat), vals in buckets.items():
            if vals:
                feats[f"{cat}_surprise"][region] = float(np.clip(np.mean(vals), -1, 1))

    # ------------------------------------------------------------------
    def _fill_levels(self, as_of, feats):
        if self._indic_off:
            return
        lag = int(get_param({}, "macro_pub_lag_days"))
        cutoff = (as_of - pd.Timedelta(days=lag)).strftime("%Y-%m-%d")
        codes = (MACRO_INDICATORS["growth"] + MACRO_INDICATORS["inflation"]
                 + MACRO_INDICATORS["real_rate"])
        resp = (self.sb.schema("raw").table("macro_indicators")
                .select("country_iso3, indicator_code, period_date, value")
                .in_("indicator_code", codes)
                .lte("period_date", cutoff).execute())
        rows = resp.data or []
        if not rows:
            return
        df = pd.DataFrame(rows)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["region"] = df["country_iso3"].map(region_of_country)
        df = df.dropna(subset=["value"])

        growth_code = MACRO_INDICATORS["growth"][0]      # gdp_growth_annual
        infl_code = MACRO_INDICATORS["inflation"][0]
        rate_code = MACRO_INDICATORS["real_rate"][0]

        # dernière (+ avant-dernière) valeur par pays×indicateur, agrégées par région
        per_region = {r: {"growth": [], "growth_trend": [], "inflation": [], "real_rate": []}
                      for r in REGIONS}
        for (iso3, code), g in df.groupby(["country_iso3", "indicator_code"]):
            region = region_of_country(iso3)
            if region not in REGIONS:
                continue
            g = g.sort_values("period_date")
            last = g["value"].iloc[-1]
            prev = g["value"].iloc[-2] if len(g) >= 2 else np.nan
            if code == growth_code:
                per_region[region]["growth"].append(last)
                if np.isfinite(prev):
                    per_region[region]["growth_trend"].append(last - prev)
            elif code == infl_code:
                per_region[region]["inflation"].append(last)
            elif code == rate_code:
                per_region[region]["real_rate"].append(last)

        # normalisation douce (tanh d'échelles fixes) + agrégat global
        def norm(key, vals):
            if not vals:
                return np.nan
            m = float(np.nanmean(vals))
            scale = {"growth": 4.0, "growth_trend": 2.0, "inflation": 4.0, "real_rate": 3.0}[key]
            return float(np.tanh((m - (2.0 if key == "inflation" else 0.0)) / scale))

        for region in REGIONS:
            for key in ("growth", "growth_trend", "inflation", "real_rate"):
                v = norm(key, per_region[region][key])
                if np.isfinite(v):
                    feats[key][region] = v
        # global = moyenne des régions renseignées
        for key in ("growth", "growth_trend", "inflation", "real_rate"):
            vals = [feats[key][r] for r in REGIONS if feats[key][r] != 0.0]
            if vals:
                feats[key]["global"] = float(np.mean(vals))
