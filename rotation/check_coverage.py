"""
check_coverage.py — Diagnostic de couverture des données pour la stratégie Rotation.

À LANCER dans un environnement ayant accès à Supabase (variables SUPABASE_URL /
SUPABASE_KEY dans l'environnement ou configdata/secrets.json) :

    python -m strategies.rotation.check_coverage

Vérifie :
  1. Présence des ETF de régime (raw.tickers, type='ETF') + profondeur de prix.
  2. Profondeur historique de raw.financial_statements (min/max filing_date, #tickers)
     → détermine à partir de quelle date l'étape 4 est PIT-safe.
  3. Couverture secteur/pays des actions sur les bourses ACWI.
"""

import logging
from utils.historical_data import get_supabase_client
from .config import REGIME_ETFS, ACWI_EXCHANGES

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def check_etfs(sb):
    print("\n=== 1. ETF de régime (raw.tickers, type='ETF') ===")
    found, missing = [], []
    for role, sym in REGIME_ETFS.items():
        code, exch = sym.rsplit(".", 1)
        r = (sb.schema("raw").table("tickers").select("id, is_delisted")
             .eq("code", code).eq("exchange", exch).eq("type", "ETF").execute())
        if r.data:
            found.append(sym)
        else:
            missing.append((role, sym))
    print(f"  Présents : {len(found)}/{len(REGIME_ETFS)} → {found}")
    if missing:
        print(f"  ⚠️ MANQUANTS : {missing}")
        print("     (sync ETF requis dans l'ETL, ou ajuster REGIME_ETFS dans config.py)")


def check_financials(sb):
    print("\n=== 2. raw.financial_statements (PIT-safe étape 4) ===")
    try:
        total = (sb.schema("raw").table("financial_statements")
                 .select("id", count="exact").limit(1).execute()).count
        mn = (sb.schema("raw").table("financial_statements")
              .select("filing_date").not_.is_("filing_date", "null")
              .order("filing_date").limit(1).execute()).data
        mx = (sb.schema("raw").table("financial_statements")
              .select("filing_date").not_.is_("filing_date", "null")
              .order("filing_date", desc=True).limit(1).execute()).data
        n_null = (sb.schema("raw").table("financial_statements")
                  .select("id", count="exact").is_("filing_date", "null")
                  .limit(1).execute()).count
        print(f"  Lignes totales      : {total}")
        print(f"  filing_date min/max : {mn[0]['filing_date'] if mn else '?'} → "
              f"{mx[0]['filing_date'] if mx else '?'}")
        print(f"  filing_date NULL    : {n_null}  (⚠️ non PIT-safe → à exclure)")
        if mn:
            print(f"  → backtest PIT-safe recommandé à partir de ~{mn[0]['filing_date'][:4]}")
    except Exception as e:
        print(f"  Erreur : {e}")


def check_sectors(sb):
    print("\n=== 3. Couverture secteur (source = fundamentals_snapshot) ===")
    total = (sb.schema("raw").table("tickers").select("id", count="exact")
             .in_("exchange", ACWI_EXCHANGES).eq("type", "Common Stock")
             .limit(1).execute()).count
    tickers_sect = (sb.schema("raw").table("tickers").select("id", count="exact")
                    .in_("exchange", ACWI_EXCHANGES).eq("type", "Common Stock")
                    .not_.is_("sector", "null").limit(1).execute()).count
    print(f"  Actions ACWI                 : {total}")
    print(f"  Avec secteur dans raw.tickers : {tickers_sect}  "
          f"(souvent ~0 → on enrichit via fundamentals_snapshot)")
    try:
        snap_sect = (sb.schema("raw").table("fundamentals_snapshot")
                     .select("ticker_id", count="exact")
                     .not_.is_("sector", "null").limit(1).execute()).count
        print(f"  Lignes fundamentals_snapshot avec secteur : {snap_sect}")
        if not snap_sect:
            print("  ⚠️ Aucun secteur en base → baromètre dégénéré. Lancer la sync fundamentals (ETL).")
    except Exception as e:
        print(f"  fundamentals_snapshot : erreur {e}")


def main():
    sb = get_supabase_client()
    check_etfs(sb)
    check_financials(sb)
    check_sectors(sb)
    print("\nDiagnostic terminé.")


if __name__ == "__main__":
    main()
