"""
data_etf.py — Chargement du panel d'ETF servant à la détection de régime (étape 1).

Réutilise `utils.historical_data.get_swiss_equities_dataframe` avec
`security_types=['ETF']` et un `ticker_filter` restreint aux ETF de régime. Le panel
est CHARGÉ UNE FOIS (petit : ~20 séries) puis tranché point-in-time (`<= as_of`) par
l'optimiseur — aucun look-ahead.

Les ETF de régime sont chargés en USD (devise native ; les signaux de régime décrivent
des dynamiques de marché et sont indépendants de la devise du portefeuille).
"""

import logging
import pandas as pd

from utils import historical_data as hd
from .config import REGIME_ETFS

logger = logging.getLogger(__name__)


def load_regime_etf_panel(start_date: str, as_of: str, source: str = "auto",
                          etfs: dict = None) -> pd.DataFrame:
    """Charge les prix ajustés (USD) des ETF de régime sur [start_date, as_of].

    Returns
    -------
    pd.DataFrame
        index = dates, colonnes = symboles ETF (CODE.US). Colonnes manquantes en base
        simplement absentes (dégradation gracieuse côté moteur de régime).
    """
    etfs = etfs or REGIME_ETFS
    symbols = sorted(set(etfs.values()))
    exchanges = sorted({s.rsplit(".", 1)[-1] for s in symbols})

    df = hd.get_swiss_equities_dataframe(
        as_of=as_of,
        source=source,
        exchanges=exchanges,
        portfolio_currency="USD",
        start_date=start_date,
        security_types=["ETF"],
        include_delisted=False,
        ticker_filter=symbols,
    )

    present = [s for s in symbols if s in df.columns]
    missing = [s for s in symbols if s not in df.columns]
    if missing:
        logger.warning("ETF de régime absents en base (ignorés) : %s", missing)
    logger.info("Panel ETF régime : %d dates × %d/%d ETF présents",
                df.shape[0], len(present), len(symbols))
    return df[present] if present else df
