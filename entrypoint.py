#!/usr/bin/env python3
"""
Point d'entrée unique pour Railway.
Utilise la variable RUN_MODE pour déterminer quel script exécuter.
"""

import os
import sys
import subprocess


def main():
    run_mode = os.getenv("RUN_MODE", "portfolio")

    print("=== RAILWAY ENTRYPOINT ===")
    print(f"RUN_MODE: {run_mode}")
    print("=" * 30)

    if run_mode == "portfolio":
        script = "run_daily_portfolio.py"
        print(f"Execution : python {script}")
        sys.exit(subprocess.run([sys.executable, script]).returncode)

    elif run_mode == "backtest":
        script = "run_backtest.py"
        print(f"Execution : python {script}")
        sys.exit(subprocess.run([sys.executable, script]).returncode)

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
