"""
data_meta.py — Métadonnées titres (secteur, pays, région) pour le baromètre.

Le secteur/pays sont quasi-statiques → chargés une fois et réutilisés à chaque
rebalancement. La région est dérivée du code de bourse (config.region_of).

⚠️ Le secteur n'est PAS fiable dans `raw.tickers.sector` (souvent NULL). La source
peuplée est `raw.fundamentals_snapshot.sector` (EODHD General.Sector, taxonomie Yahoo
qui correspond aux clés de config.SECTOR_BIAS). On enrichit donc depuis le snapshot ;
le secteur étant quasi-statique, utiliser le dernier connu est acceptable (≈ aucun
look-ahead matériel sur une classification sectorielle).
"""

import logging
import pandas as pd

from utils.historical_data import get_supabase_client
from .config import region_of

logger = logging.getLogger(__name__)


def _load_sector_from_snapshot(sb, ids) -> dict:
    """ticker_id → sector depuis raw.fundamentals_snapshot (dernier non-NULL gagne)."""
    sect = {}
    try:
        for i in range(0, len(ids), 1000):
            chunk = ids[i:i + 1000]
            resp = (sb.schema("raw").table("fundamentals_snapshot")
                    .select("ticker_id, sector").in_("ticker_id", chunk).execute())
            for r in (resp.data or []):
                if r.get("sector"):
                    sect[r["ticker_id"]] = r["sector"]
    except Exception as e:
        logger.warning("Enrichissement secteur (fundamentals_snapshot) échoué : %s", e)
    return sect


def load_stock_metadata(exchanges, include_delisted: bool = True,
                        security_types=None) -> pd.DataFrame:
    """Charge les métadonnées des actions de l'univers.

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
             .select("id, code, exchange, type, sector, industry, country, is_delisted")
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

    # Enrichissement secteur depuis fundamentals_snapshot là où tickers.sector est NULL
    if "sector" not in df.columns:
        df["sector"] = None
    null_mask = df["sector"].isna()
    if null_mask.any():
        ids = df.loc[null_mask, "id"].dropna().tolist()
        sect_map = _load_sector_from_snapshot(sb, ids)
        if sect_map:
            df.loc[null_mask, "sector"] = df.loc[null_mask, "id"].map(sect_map)
            logger.info("Secteur enrichi depuis fundamentals_snapshot : %d titres", len(sect_map))

    df["sector"] = df["sector"].fillna("Unknown")
    df["category"] = df["sector"].astype(str) + "|" + df["region"].astype(str)
    logger.info("Métadonnées : %d titres, %d secteurs, %d régions",
                len(df), df["sector"].nunique(), df["region"].nunique())
    return df[["sector", "industry", "country", "exchange", "region", "category"]]
