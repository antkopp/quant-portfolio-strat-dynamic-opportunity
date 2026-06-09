"""
data_meta.py — Métadonnées titres (secteur GICS, pays, région) pour le baromètre.

Le secteur/pays sont quasi-statiques → chargés une fois depuis `raw.tickers` et
réutilisés à chaque rebalancement. La région est dérivée du code de bourse
(voir config.region_of).
"""

import logging
import pandas as pd

from utils.historical_data import get_supabase_client
from .config import region_of

logger = logging.getLogger(__name__)


def load_stock_metadata(exchanges, include_delisted: bool = True,
                        security_types=None) -> pd.DataFrame:
    """Charge les métadonnées des actions de l'univers depuis raw.tickers.

    Returns
    -------
    pd.DataFrame indexé par `symbol` (CODE.EXCHANGE), colonnes :
        sector, industry, country, exchange, region, category (= sector|region).
    """
    if security_types is None:
        security_types = ["Common Stock"]

    sb = get_supabase_client()
    rows, offset, batch = [], 0, 1000
    while True:
        q = (sb.schema("raw").table("tickers")
             .select("code, exchange, type, sector, industry, country, is_delisted")
             .in_("exchange", list(exchanges))
             .in_("type", list(security_types)))
        if not include_delisted:
            q = q.eq("is_delisted", False)
        resp = q.range(offset, offset + batch - 1).execute()
        if not resp.data:
            break
        rows.extend(resp.data)
        if len(resp.data) < batch:
            break
        offset += batch

    if not rows:
        logger.warning("Aucune métadonnée titre trouvée pour exchanges=%s", exchanges)
        return pd.DataFrame(columns=["sector", "industry", "country", "exchange",
                                     "region", "category"])

    df = pd.DataFrame(rows)
    df["symbol"] = df["code"] + "." + df["exchange"]
    df = df.drop_duplicates(subset="symbol").set_index("symbol")
    df["region"] = df.index.to_series().map(region_of)
    df["sector"] = df["sector"].fillna("Unknown")
    df["category"] = df["sector"].astype(str) + "|" + df["region"].astype(str)
    logger.info("Métadonnées : %d titres, %d secteurs, %d régions",
                len(df), df["sector"].nunique(), df["region"].nunique())
    return df[["sector", "industry", "country", "exchange", "region", "category"]]
