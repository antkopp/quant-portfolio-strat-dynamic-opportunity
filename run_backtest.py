"""
run_backtest.py — Backtest d'amorçage « Dynamic Opportunity ».

    python run_backtest.py                # backtest + sauvegarde Supabase
    python run_backtest.py --dry-run      # sans sauvegarde
    python run_backtest.py --no-costs     # sans coûts de transaction

RUN_MODE=backtest dans entrypoint.py route ici.
"""

import argparse
import logging
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


def main():
    parser = argparse.ArgumentParser(description="Backtest Dynamic Opportunity")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-costs", action="store_true")
    args = parser.parse_args()

    params = APP_PARAMS
    if args.no_costs:
        params["backtest"]["include_transaction_costs"] = False

    strat_full = _strategy_name(params)
    logger.info("=" * 60)
    logger.info("Dynamic Opportunity — Backtest")
    logger.info(f"Stratégie : {strat_full}")
    logger.info(f"Régime    : {params['optimizer']['rotation']['regime_method']}")
    logger.info(f"Période   : {params['start_date']} → {datetime.now():%Y-%m-%d}")
    logger.info("=" * 60)

    import portfolio_construction.backtest as bt
    from rotation.runner import build_optimizer_fn

    optimizer_fn = build_optimizer_fn(params)

    t0 = datetime.now()
    (portfolio_weights, portfolio_returns, portfolio_value, assets_cum_returns,
     asset_returns, metrics, hist_prices, hist_volumes) = \
        bt.run_portfolio_backtest(optimizer_fn=optimizer_fn, params=params)
    elapsed = (datetime.now() - t0).total_seconds()

    logger.info(f"Backtest terminé en {elapsed/60:.1f} min")
    logger.info(f"  Return annualisé : {metrics.get('annualized_return', 0)*100:.2f}%")
    logger.info(f"  Volatilité       : {metrics.get('annualized_vol', 0)*100:.2f}%")
    logger.info(f"  Sharpe           : {metrics.get('annualized_sharpe', 0):.2f}")
    logger.info(f"  Max Drawdown     : {metrics.get('max_drawdown', 0)*100:.2f}%")

    if not args.dry_run:
        from supabase_files.backtest_storage import save_backtest_results
        run_id = save_backtest_results(
            portfolio_weights=portfolio_weights,
            portfolio_returns=portfolio_returns,
            portfolio_value=portfolio_value,
            metrics=metrics,
            run_name=strat_full,
            strategy_name=(f"{strat_full}_{params['universe']['portfolio_currency']}"
                           f"_{params['backtest']['rebalance_frequency']}_Portfolio"),
            universe_name=params["universe"]["universe_name"],
            portfolio_currency=params["universe"]["portfolio_currency"],
            parameters={
                "start_date": params["start_date"],
                "end_date": datetime.now().strftime("%Y-%m-%d"),
                "source": params["source"],
                "mode": "backtest_seed",
                "regime_method": params["optimizer"]["rotation"]["regime_method"],
                "executed_at": datetime.now().isoformat(),
                "execution_time_seconds": elapsed,
                **params["backtest"],
            },
            overwrite=True,
        )
        logger.info(f"Résultats sauvegardés : {run_id}")

    logger.info("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
