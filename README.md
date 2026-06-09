# quant-portfolio-strat-dynamic-opportunity

Stratégie **« Dynamic Opportunity »** — rotation **Risk On / Risk Off**, actions only
(ETF exclus de l'investissable), univers **ACWI**, 10–20 lignes. Se branche sur le moteur
de backtest partagé [`quant-portfolio-base`](https://github.com/antkopp/quant-portfolio-base)
(installé via `requirements.txt`, comme les autres stratégies).

## Pipeline en 4 étapes (`rotation/`)

1. **`regime.py`** — revue de marché : détection de régime Risk On/Off à partir d'ETF
   (momentum large, ratio cycliques/défensifs, courbe, crédit, or, USD, EM/DM). Moteurs
   *pluggables* : `rules` (défaut, causal/PIT-safe) · `hmm` (Gaussian HMM) · `causal` (stub).
2. **`barometer.py`** — grille catégorie (**secteur GICS × région** NA/EU/ADM/EM) ×
   {défensif / neutre / offensif}, modulée par le score de régime.
3. **`allocation.py`** — budgets cibles par catégorie (water-filling sous plafonds
   catégorie/région, Σ=1).
4. **`selection.py`** — analyse des positions : composite **fondamental PIT** (qualité +
   croissance, depuis `raw.financial_statements` filtré par `filing_date`) + momentum prix
   → 10–20 titres, plafond par position.

`rotation/runner.py` assemble le tout en `build_optimizer_fn(params) -> optimizer_fn`
(contrat du moteur de la base).

## Rebalancement hybride (hebdo + quotidien)

La cadence moteur est **quotidienne** (`rebalance_frequency: "B"`). Un **cache d'état**
dans le runner décide du rebalancement réel :
- ancre calendaire tous les `base_rebal_days` jours (défaut 7 = hebdo), **ou**
- **bascule de régime** Risk On↔Off détectée ce jour-là (déclenchement événementiel).

Aucune modification du moteur partagé n'est requise (même approche que les autres strats
à rebalancement dynamique).

## Exécution

```bash
python -m rotation.check_coverage   # diagnostic données (ETF régime, financial_statements)
python run_backtest.py --dry-run    # backtest sans sauvegarde
python run_backtest.py              # backtest + sauvegarde Supabase
python run_daily_portfolio.py       # run quotidien (production)
pytest tests/ -q                    # tests unitaires offline (logique pure)
```

Déploiement Railway via `entrypoint.py` (`RUN_MODE` = `portfolio` | `backtest` | `track_record`).
Variables requises : `SUPABASE_URL`, `SUPABASE_KEY`, accès R2 (mode `data_access: pit`),
`GITHUB_TOKEN` (build, pour installer la base privée). Overrides via env : voir
`config_overrides.py`.

## Mise à jour de la base

Le workflow `.github/workflows/update-base-hash.yml` réécrit automatiquement le SHA de
`quant-portfolio-base` dans `requirements.txt` sur dispatch `base-updated`.
