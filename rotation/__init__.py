"""
Stratégie « Rotation / Risk On–Risk Off » — pipeline d'investissement en 4 étapes.

1. regime.py     : revue de marché → détection de régime (Risk On / Risk Off) via ETF.
2. barometer.py  : grille catégorie (secteur × région) → score défensif/neutre/offensif.
3. allocation.py : traduction du baromètre en budgets cibles par catégorie.
4. selection.py  : analyse fondamentale PIT des constituants → poids actions finaux.

Le tout est branché sur le moteur de backtest existant via une closure
(`optimizer.build_rotation_optimizer`) qui respecte le contrat
`optimizer_fn(prices, params) -> pd.Series(poids)` sans modifier le moteur partagé.
"""
