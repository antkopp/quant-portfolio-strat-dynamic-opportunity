"""
run_daily_portfolio.py — Exécution quotidienne « Dynamic Opportunity » (production).

Relance le backtest complet et met à jour positions + performances en base.
RUN_MODE=portfolio dans entrypoint.py route ici.

    python run_daily_portfolio.py            # run + sauvegarde
    python run_daily_portfolio.py --dry-run  # sans sauvegarde
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import yaml
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
for _noisy in ("httpx", "httpcore", "urllib3", "requests"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_config_path = Path(__file__).parent / "configdata" / "params.yaml"
with open(_config_path, "r", encoding="utf-8") as _f:
    APP_PARAMS = yaml.safe_load(_f)

from config_overrides import apply_env_overrides
apply_env_overrides(APP_PARAMS)


def _strategy_name(params: dict) -> str:
    u = params["universe"]
    base = u.get("strategy_name", "DynamicOpportunity")
    variant = u.get("strategy_variant", "")
    suffix = f"_{variant}" if variant else ""
    return f"{base}_{u['universe_name']}{suffix}"


def run_backtest(dry_run: bool = False, run_name: str = None) -> dict:
    strat_full = _strategy_name(APP_PARAMS)
    rebalance_frequency = APP_PARAMS["backtest"]["rebalance_frequency"]
    portfolio_currency = APP_PARAMS["universe"]["portfolio_currency"]
    strategy_name = f"{strat_full}_{portfolio_currency}_{rebalance_frequency}_Portfolio"

    logger.info(f"Dynamic Opportunity daily ({APP_PARAMS['start_date']} → "
                f"{datetime.now():%Y-%m-%d}, source={APP_PARAMS['source']})")

    try:
        import portfolio_construction.backtest as bt
        from rotation.runner import build_optimizer_fn
        from supabase_files.backtest_storage import save_backtest_results

        optimizer_fn = build_optimizer_fn(APP_PARAMS)

        t0 = datetime.now()
        (portfolio_weights, portfolio_returns, portfolio_value, assets_cum_returns,
         asset_returns, metrics, hist_prices, hist_volumes) = \
            bt.run_portfolio_backtest(optimizer_fn=optimizer_fn, params=APP_PARAMS)
        elapsed = (datetime.now() - t0).total_seconds()

        logger.info(f"Backtest terminé en {elapsed:.1f}s "
                    f"(Sharpe={metrics.get('annualized_sharpe', 0):.2f}, "
                    f"MaxDD={metrics.get('max_drawdown', 0)*100:.1f}%)")

        run_id = None
        if not dry_run:
            run_id = save_backtest_results(
                portfolio_weights=portfolio_weights,
                portfolio_returns=portfolio_returns,
                portfolio_value=portfolio_value,
                metrics=metrics,
                run_name=run_name,
                strategy_name=strategy_name,
                universe_name=APP_PARAMS["universe"]["universe_name"],
                portfolio_currency=portfolio_currency,
                parameters={
                    "start_date": APP_PARAMS["start_date"],
                    "end_date": datetime.now().strftime("%Y-%m-%d"),
                    "source": APP_PARAMS["source"],
                    "executed_at": datetime.now().isoformat(),
                    "execution_time_seconds": elapsed,
                    "strategy_name": APP_PARAMS["universe"]["strategy_name"],
                    "strategy_variant": APP_PARAMS["universe"].get("strategy_variant", ""),
                    "regime_method": APP_PARAMS["optimizer"]["rotation"]["regime_method"],
                    "exchanges": APP_PARAMS["universe"]["exchanges"],
                    **APP_PARAMS["backtest"],
                },
                overwrite=True,
            )
            logger.info(f"Sauvegardé : {run_id}")

        return {"success": True, "run_id": run_id, "metrics": metrics, "elapsed_seconds": elapsed}

    except Exception as e:
        logger.error(f"Erreur backtest: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Dynamic Opportunity daily portfolio")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Dynamic Opportunity — Daily Update")
    logger.info(f"{datetime.now():%Y-%m-%d %H:%M:%S}")
    logger.info("=" * 60)

    if not args.dry_run:
        missing = [v for v in ("SUPABASE_URL", "SUPABASE_KEY") if not os.getenv(v)]
        if missing:
            logger.error(f"Variables manquantes: {', '.join(missing)}")
            sys.exit(1)

    run_name = _strategy_name(APP_PARAMS)
    logger.info(f"run_name = {run_name}")

    result = run_backtest(dry_run=args.dry_run, run_name=run_name)
    status = "OK" if result.get("success") else "ERREUR"
    logger.info(f"{status} — success={result.get('success')}")
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
