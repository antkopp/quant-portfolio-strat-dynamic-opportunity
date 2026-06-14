#!/usr/bin/env python3
"""
Point d'entrée unique pour Railway.
Utilise la variable RUN_MODE pour déterminer quel script exécuter.

PORTFOLIO_CURRENCY accepte une LISTE ("USD,CHF,EUR") : les modes 'portfolio' et 'backtest'
sont exécutés une fois PAR devise (sous-processus isolé), produisant autant de backtests
distincts en base. Un cache Parquet partagé est utilisé -> téléchargement R2 une seule fois.
"""

import os
import sys
import shutil
import tempfile
import subprocess


def _currencies():
    """Liste de devises depuis PORTFOLIO_CURRENCY (CSV). Vide -> [None] = devise de la config."""
    raw = os.getenv('PORTFOLIO_CURRENCY', '') or ''
    ccys = []
    for c in raw.split(','):
        c = c.strip().upper()
        if c and c not in ccys:
            ccys.append(c)
    return ccys or [None]


def _run_per_currency(script):
    """Exécute `script` une fois par devise (sous-processus isolé). Non-zero si échec.

    En multi-devises, un cache Parquet partagé (SQP_PARQUET_CACHE) est passé aux
    sous-processus -> le Parquet R2 n'est téléchargé qu'une seule fois."""
    currencies = _currencies()
    cache_dir = tempfile.mkdtemp(prefix="sqp_parquet_cache_") if len(currencies) > 1 else None
    failures = []
    try:
        for ccy in currencies:
            env = os.environ.copy()
            if ccy:
                env['PORTFOLIO_CURRENCY'] = ccy
            if cache_dir:
                env['SQP_PARQUET_CACHE'] = cache_dir
            print("=" * 30)
            print(f"Devise: {ccy or '(defaut config)'}  ->  python {script}")
            print("=" * 30)
            rc = subprocess.run([sys.executable, script], env=env).returncode
            if rc != 0:
                failures.append((ccy, rc))
    finally:
        if cache_dir:
            shutil.rmtree(cache_dir, ignore_errors=True)
    if failures:
        print(f"ECHEC sur {len(failures)} devise(s): {failures}")
        return 1
    return 0


def main():
    run_mode = os.getenv("RUN_MODE", "portfolio")

    print("=== RAILWAY ENTRYPOINT ===")
    print(f"RUN_MODE: {run_mode}")
    print("=" * 30)

    if run_mode == "portfolio":
        sys.exit(_run_per_currency("run_daily_portfolio.py"))

    elif run_mode == "backtest":
        sys.exit(_run_per_currency("run_backtest.py"))

    elif run_mode == "track_record":
        from supabase_files.track_record_update import daily_update_track_record
        success = daily_update_track_record()
        sys.exit(0 if success else 1)

    else:
        print(f"RUN_MODE inconnu: {run_mode}")
        print("Valeurs acceptées: 'portfolio', 'backtest', 'track_record'")
        sys.exit(1)


if __name__ == "__main__":
    main()
