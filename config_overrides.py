"""
config_overrides.py — Application centralisée des overrides d'environnement Railway.

Permet de piloter la stratégie depuis les variables d'env du service Railway sans
modifier configdata/params.yaml.
"""

import os


def _as_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def apply_env_overrides(params: dict) -> dict:
    """Applique les overrides d'environnement in-place et retourne params."""

    # --- Univers ---
    u = params.setdefault("universe", {})
    if os.getenv("UNIVERSE_NAME"):
        u["universe_name"] = os.getenv("UNIVERSE_NAME")
    if os.getenv("PORTFOLIO_CURRENCY"):
        u["portfolio_currency"] = os.getenv("PORTFOLIO_CURRENCY")
    if os.getenv("EXCHANGES"):
        u["exchanges"] = [e.strip() for e in os.getenv("EXCHANGES").split(",")]
    if os.getenv("STRATEGY_NAME"):
        u["strategy_name"] = os.getenv("STRATEGY_NAME")
    if os.getenv("STRATEGY_VARIANT"):
        u["strategy_variant"] = os.getenv("STRATEGY_VARIANT")

    # --- Source / backtest ---
    if os.getenv("SOURCE"):
        params["source"] = os.getenv("SOURCE")
    bt = params.setdefault("backtest", {})
    if os.getenv("DATA_ACCESS"):
        bt["data_access"] = os.getenv("DATA_ACCESS")
    if os.getenv("REBALANCE_FREQUENCY"):
        bt["rebalance_frequency"] = os.getenv("REBALANCE_FREQUENCY")
    if os.getenv("START_DATE"):
        params["start_date"] = os.getenv("START_DATE")

    # --- Paramètres rotation ---
    rot = params.setdefault("optimizer", {}).setdefault("rotation", {})
    if os.getenv("REGIME_METHOD"):
        rot["regime_method"] = os.getenv("REGIME_METHOD")         # rules | hmm | causal
    if os.getenv("BASE_REBAL_DAYS"):
        rot["base_rebal_days"] = int(os.getenv("BASE_REBAL_DAYS"))
    if os.getenv("TARGET_POSITIONS_MIN"):
        rot["target_positions_min"] = int(os.getenv("TARGET_POSITIONS_MIN"))
    if os.getenv("TARGET_POSITIONS_MAX"):
        rot["target_positions_max"] = int(os.getenv("TARGET_POSITIONS_MAX"))
    if os.getenv("MAX_POSITION_WEIGHT"):
        rot["max_position_weight"] = float(os.getenv("MAX_POSITION_WEIGHT"))
    if os.getenv("SELECTION_FUNDAMENTAL_WEIGHT"):
        rot["selection_fundamental_weight"] = float(os.getenv("SELECTION_FUNDAMENTAL_WEIGHT"))
    if os.getenv("REGIME_ON_THRESHOLD"):
        rot["regime_on_threshold"] = float(os.getenv("REGIME_ON_THRESHOLD"))
    if os.getenv("REGIME_OFF_THRESHOLD"):
        rot["regime_off_threshold"] = float(os.getenv("REGIME_OFF_THRESHOLD"))

    return params
