# KID — Stratégie Dynamic Opportunity (Key Information Document)

> Fiche produit exhaustive de la stratégie de **rotation Risk On / Risk Off** par baromètre
> sectoriel × géographique. Décrit l'état EXACT du code (repo
> `quant-portfolio-strat-dynamic-opportunity`, branche `main`), formules incluses.
> Document de référence — rien n'est omis.

---

## 1. Identité

| Champ | Valeur |
|-------|--------|
| Nom | Dynamic Opportunity |
| Nature | Rotation Risk On/Off, **long-only**, actions sélectionnées par catégorie favorisée |
| Univers investissable | **Actions uniquement** (ETF EXCLUS de l'investissable), bourses ACWI via env `EXCHANGES` |
| Rôle des ETF | **Lecture de marché seulement** (détection de régime) — jamais détenus |
| Nb de lignes | **10 à 20** positions |
| Devise | USD (portefeuille) ; ETF de régime lus en USD natif |
| Cadence | **Quotidienne** (`rebalance_frequency="B"`) + **décision de rebal INTERNE** : ancre hebdo (`base_rebal_days`) **ou** bascule de régime |
| Détection régime | Moteurs *pluggables* : `rules` (défaut, causal) · `hmm` (Gaussian HMM) · `causal` (stub) |
| Plateforme | Railway (exécution) · Supabase (persistance) · R2/EODHD (données) |
| Dépendance | `quant-portfolio-base` (moteur de backtest, épinglé par hash) |
| Tables propres | aucune — réutilise `portfolio_*` (partagées, différenciées par `strategy_name`) |

---

## 1bis. La stratégie expliquée simplement (pour néophyte)

### L'idée en une phrase
Le marché alterne des phases **« Risk On »** (les investisseurs prennent du risque : les
secteurs **cycliques/offensifs** — tech, conso discrétionnaire, industrie — montent) et des
phases **« Risk Off »** (fuite vers la sécurité : les secteurs **défensifs** — santé,
consommation de base, services aux collectivités — surperforment). On **détecte dans quelle
phase on est**, on **penche le portefeuille du bon côté**, et dans chaque case favorisée on
**choisit les meilleures entreprises** par leurs fondamentaux. On ré-ajuste **chaque semaine**,
et **immédiatement** dès que la phase bascule.

### Pourquoi c'est pertinent (et comment on s'y prend)
Les rotations sectorielles sont une régularité bien documentée du cycle. Le défi est
**double** : (1) reconnaître la phase **sans regarder l'avenir**, et (2) traduire « on est en
Risk On » en un portefeuille concret de 10-20 actions. On résout (1) avec un **thermomètre de
marché** lu sur des ETF (instruments larges, liquides, sans biais de sélection), et (2) avec un
**baromètre** en grille (secteur × région) puis une **analyse fondamentale** des candidats.

### Le parcours, étape par étape (le fil rouge)

1. **Revue de marché** (`ÉTAPE 1`). On calcule un **score de régime ∈ [−1, +1]** (+1 = Risk On
   franc, −1 = Risk Off franc) à partir de plusieurs « capteurs » de marché sur ETF : le
   marché monte-t-il ? les cycliques battent-ils les défensives ? le crédit risqué
   surperforme-t-il ? l'or et le dollar (refuges) montent-ils ? *Lien :* ce score unique
   **oriente tout le reste**.

2. **Le baromètre** (`ÉTAPE 2`). On dresse une grille : en lignes les **catégories**
   (secteur × région : Amérique du Nord, Europe, Asie développée, émergents), en colonnes
   **défensif / neutre / offensif**. Chaque case reçoit un **tilt** = (sa nature offensive ou
   défensive **× le score de régime**) + (sa **force relative** récente). *Lien :* en Risk On
   les cases offensives s'allument ; en Risk Off, les défensives.

3. **La traduction en budgets** (`ÉTAPE 3`). On retient les meilleures cases et on leur donne
   un **budget** (% du portefeuille) proportionnel à leur tilt, en respectant des **plafonds**
   par case et par région (diversification). *Lien :* on passe d'un classement de cases à une
   allocation chiffrée.

4. **Le choix des actions** (`ÉTAPE 4`). Dans chaque case dotée d'un budget, on **classe les
   entreprises** par un score **fondamental** (rentabilité + croissance, calculé *point-in-time*
   pour ne pas tricher) **+ momentum** de prix, et on garde les meilleures jusqu'à atteindre
   **10-20 lignes**. *Lien :* le budget d'une case est réparti entre ses meilleures actions.

### Le rythme (hebdo + quotidien)
On recalcule la cible **chaque semaine**. Mais on **surveille le régime tous les jours** : si
la phase **bascule** (Risk On→Off ou l'inverse) un mardi, on **ne attend pas** le lundi
suivant — on rebalance **le jour même**. Entre deux décisions, le portefeuille **dérive
naturellement** (le moteur gère).

> **En résumé** : *lire la phase de marché → pencher la grille → budgéter les cases →
> choisir les meilleures actions ; ré-évaluer chaque semaine et à chaque bascule.*

---

## 2. Fondement théorique

### 2.1 Le cycle Risk On / Risk Off et la rotation sectorielle
En régime d'appétit pour le risque (**Risk On**), les actifs risqués et les secteurs
**cycliques** (Technology, Consumer Cyclical, Industrials, Basic Materials, Energy, Financials)
surperforment ; en **Risk Off**, les capitaux refluent vers les **défensifs** (Consumer
Defensive, Utilities, Healthcare) et les refuges (or, USD, duration longue). Cette alternance
est captée par des **signaux market-based** observables sur ETF (pas de fondamental retardé).

### 2.2 Le baromètre comme transcription du régime
Chaque secteur a un **biais statique** sur l'axe défensif(−1)↔offensif(+1). Multiplié par le
score de régime, il donne la direction du tilt ; on y ajoute la **force relative dynamique**
(momentum du panier de la catégorie) pour capter la rotation **déjà en cours**. La grille
secteur × région évite la dominance d'une seule géographie.

### 2.3 Thèse d'investissement
> On ne prédit pas le marché, on **s'aligne sur sa phase**. Le régime (étape 1) décide du
> *côté* (offensif vs défensif) ; le baromètre (étape 2-3) décide de *quelles cases* ; les
> fondamentaux (étape 4) décident de *quelles actions* dans ces cases. Le portefeuille reste
> concentré (10-20 noms), diversifié par région, et réactif (rebal hebdo + sur bascule).

---

## 3. Données (INPUT)

| Élément | Détail |
|---------|--------|
| Source | R2 Cloudflare (Parquet) / Supabase, alimentés par EODHD via le repo ETL |
| Prix actions | univers ACWI, `Common Stock` ; convertis en **USD** ; filtre 252 obs min |
| ETF de régime | ~18 ETF US (SPY, secteurs SPDR, TLT/IEF, HYG/LQD, GLD, UUP, EEM/EFA), USD natif |
| Métadonnées | `raw.tickers` : **secteur**, industrie, **pays**, type, ISIN → catégorie = secteur \| région |
| Fondamentaux | **`raw.financial_statements`** (annuel), filtré par **`filing_date ≤ as_of`** (PIT-safe) |
| Anti-look-ahead | prix tronqués à `as_of` ; fondamentaux gated par `filing_date` ; régime causal (rules) |
| Anti-survivorship | `include_delisted: true` (titres délistés présents de leur vivant) |

> ⚠️ On n'utilise **jamais** `raw.fundamentals_snapshot` au backtest (il ne contient que le
> DERNIER état connu → look-ahead). La source PIT est `financial_statements` (`filing_date`).

---

## 4. PROCESS — le pipeline, étape par étape

Branché sur le moteur de la base via `rotation/runner.py:build_optimizer_fn` →
`optimizer_fn(hist_prices, params) → pd.Series(poids)`. `hist_prices` est tronqué à `as_of`
(aucun look-ahead). Le contexte (panel ETF, métadonnées, accès fondamental) est **pré-chargé
une fois**.

### ÉTAPE 0 — Réduction de l'univers (liquidité, STRATIFIÉE par bourse)
```
score = moyenne( prix × volume ) sur adtv_lookback_days (63 j)         [metric = adtv]
univers retenu = top_n_per_exchange (100) titres les + liquides PAR BOURSE
garde-fou mémoire = max_per_exchange (200) titres/bourse  (anti-OOM, mode PIT)
```
→ diversification géographique, pas de domination US. *(fait par le moteur de la base.)*

### ÉTAPE 1 — Revue de marché / détection de régime (`rotation/regime.py`)
Score continu **∈ [−1, +1]** lu sur le panel d'ETF tranché à `as_of`. Moteur `rules` (défaut) :
chaque sous-signal est borné par `tanh` d'un **z-score glissant** d'un **momentum multi-horizon**
(`lookbacks=[21,63,126]`, fenêtre z = 252 j), puis combiné en moyenne pondérée et **lissé EWM**
(`halflife=5`).
```
sous-signal(x)   = moyenne_lb[ tanh( zscore_252( x/x.shift(lb) − 1 ) ) ]
broad_momentum   = sous-signal( SPY )
cyc_def_ratio    = sous-signal( panier_cycliques / panier_défensifs )
curve            = sous-signal( IEF / TLT )       (bons courts > longs = taux ↑ = Risk On)
credit           = sous-signal( HYG / LQD )       (HY > IG = Risk On)
em_dm            = sous-signal( EEM / EFA )        (EM > DM = Risk On)
gold             = − sous-signal( GLD )            (or fort = Risk Off)
usd              = − sous-signal( UUP )            (USD fort = Risk Off)

score = EWM_halflife( Σ_i w_i·sous-signal_i / Σ_i w_i )   ∈ [−1, +1]   (clip)
label = risk_on  si score ≥ on_threshold (0.20)
        risk_off si score ≤ off_threshold (−0.20)
        neutral  sinon
```
> Le moteur `rules` est **strictement causal** (rolling/EWM) → PIT-safe, la série complète peut
> être pré-calculée. Les ETF absents en base sont ignorés (poids renormalisés). Moteurs
> alternatifs : `hmm` (Gaussian HMM 3 états sur rendement/vol/cyc-def, états mappés sur l'axe
> par leur rendement latent) et `causal` (stub → repli `rules`).

### ÉTAPE 2 — Baromètre catégorie × {défensif/neutre/offensif} (`rotation/barometer.py`)
Lignes = **catégories** (secteur GICS × région ∈ {NA, EU, ADM, EM}). Pour chaque catégorie
présente (≥ `min_names_per_cat` = 3 titres dans l'univers courant) :
```
biais_statique  = SECTOR_BIAS[secteur]               ∈ [−1, +1]  (offensif>0, défensif<0)
momentum_cat    = moyenne des ( prix/prix.shift(126) − 1 ) des titres de la catégorie
momentum_z      = zscore_cross-section( momentum_cat )    (clip ±3)

tilt  = w_s · (biais_statique × score_régime) + w_m · momentum_z       (w_s=w_m=0.5)
label = offensif si tilt > 0.15 ; défensif si tilt < −0.15 ; neutre sinon
```
> Modulation par le régime : en Risk On (`score>0`), les secteurs offensifs (`biais>0`)
> obtiennent un tilt positif ; en Risk Off (`score<0`), ce sont les défensifs (`biais<0`,
> car `biais×score>0`). Le momentum capte la rotation déjà engagée.

### ÉTAPE 3 — Budgets cibles par catégorie (`rotation/allocation.py`)
```
chosen   = top alloc_top_categories (8) catégories à tilt > 0 (sinon les moins négatives)
w_brut   ∝ tilt (décalé positif si nécessaire)
Σw = 1, PLAFONDS appliqués par WATER-FILLING (préserve Σ=1) :
     • par catégorie : w_i ≤ alloc_max_per_category (0.25)
     • par région    : Σ_région ≤ alloc_max_per_region (0.50)
```
> Le **water-filling** redistribue l'excédent écrêté aux items sous le plafond
> (itératif) → respecte les plafonds **sans** re-violer par renormalisation naïve.

### ÉTAPE 4 — Analyse des positions & poids finaux (`rotation/selection.py`)
Candidats = titres des catégories dotées d'un budget, présents dans le panel.
```
momentum_z  = zscore( prix/prix.shift(126) − 1 ) sur les candidats
fund_z      = composite fondamental PIT (cf. ci-dessous), z-scoré (ou absent → momentum seul)
score       = w_f · fund_z + w_m · momentum_z       (w_f=w_m=0.5)

# nb de lignes par catégorie : ∝ budget, plancher 1, plafond = candidats dispo,
# total ∈ [target_positions_min (10), target_positions_max (20)]  (largest remainder)
poids_i     = budget_catégorie / nb_lignes_retenues_dans_la_catégorie   (réparti égal)
poids       = water-filling( poids , max_position_weight (0.12) ) ;  Σ = 1
```
**Composite fondamental PIT** (`rotation/data_fundamentals.py`, depuis `financial_statements`,
`filing_date ≤ as_of`, 2 derniers exercices annuels) :
```
roe = netIncome/equity   roa = netIncome/totalAssets   net_margin = netIncome/totalRevenue
rev_growth = revenue_t/revenue_{t-1} − 1   ni_growth = netIncome_t/netIncome_{t-1} − 1
composite = moyenne des z-scores cross-section des métriques disponibles
```
> Repli **momentum seul** si aucun fondamental filé à cette date (cold-start, marchés à
> couverture fondamentale faible). `fundamentals_snapshot` réservé au portefeuille **live**.

### ÉTAPE 5 — Décision de rebalancement HYBRIDE (`rotation/runner.py`)
Le moteur appelle l'optimiseur **chaque jour** (`rebalance_frequency="B"`). Un **cache d'état**
(`weights`, `last_rebal`, `last_label`) décide du rebal RÉEL :
```
flip = (label_du_jour ≠ label_au_dernier_rebal)
due  = (premier appel) OU (jours écoulés depuis last_rebal ≥ base_rebal_days (7)) OU flip
si NON due  → renvoie les poids cachés  (le moteur gère le drift)
si due      → exécute ÉTAPES 2→4, met à jour le cache
```
> → **hebdo** (ancre `base_rebal_days`) **+ quotidien** (déclenchement sur bascule de régime),
> SANS modifier le moteur partagé (même principe que les autres strats à rebal dynamique).

---

## 5. Paramètres (référence — valeurs actuelles)

### Univers & rebalancement
| Param | Val | Rôle |
|-------|-----|------|
| `security_types` | `[Common Stock]` | actions only (ETF exclus de l'investissable) |
| `universe.exchanges` | 18 bourses ACWI | NA + EU + Asie dév. + émergents (env `EXCHANGES`) |
| `portfolio_currency` | USD | devise du portefeuille |
| `universe_filter.method` / `metric` | `top_n_per_exchange` / `adtv` | liquidité stratifiée/bourse |
| `top_n_per_exchange` / `max_per_exchange` | 100 / 200 | titres/bourse · garde-fou mémoire |
| `rebalance_frequency` | `B` | cadence moteur quotidienne (décision réelle = interne) |
| `base_rebal_days` | 7 | ancre calendaire du rebal interne (7 = hebdo) |
| `data_access` | `pit` | point-in-time (ACWI très large → anti-OOM ; nécessite R2) |
| `start_date` / `start_date_data` | 2015-01-02 / 2010-01-04 | décisions / historique chargé |

### Régime (ÉTAPE 1)
| Param | Val | Rôle |
|-------|-----|------|
| `regime_method` | `rules` | `rules` (causal) / `hmm` / `causal` (stub) |
| `regime_lookbacks` | `[21,63,126]` | horizons de momentum des sous-signaux |
| `regime_zwindow` | 252 | fenêtre du z-score glissant |
| `regime_smooth_halflife` | 5 | lissage EWM du score composite |
| `regime_on_threshold` / `regime_off_threshold` | 0.20 / −0.20 | seuils des labels |
| `regime_weights` | broad 1.0, cyc_def 1.0, credit 0.8, curve 0.6, em_dm 0.5, gold 0.4, usd 0.4 | pondération des sous-signaux (renormalisée sur les dispos) |

### Baromètre & allocation (ÉTAPES 2-3)
| Param | Val | Rôle |
|-------|-----|------|
| `barometer_momentum_lookback` | 126 | force relative des catégories |
| `barometer_static_weight` / `barometer_momentum_weight` | 0.5 / 0.5 | poids biais×régime vs momentum |
| `barometer_min_names_per_cat` | 3 | catégorie ignorée si trop peu de titres |
| `alloc_top_categories` | 8 | nb de catégories retenues |
| `alloc_max_per_category` / `alloc_max_per_region` | 0.25 / 0.50 | plafonds (water-filling) |

### Sélection (ÉTAPE 4)
| Param | Val | Rôle |
|-------|-----|------|
| `target_positions_min` / `target_positions_max` | 10 / 20 | bornes du nb de lignes |
| `selection_fundamental_weight` / `selection_momentum_weight` | 0.5 / 0.5 | poids du composite |
| `selection_momentum_lookback` | 126 | momentum prix des candidats |
| `max_position_weight` | 0.12 | plafond par position (water-filling) |

### Coûts (moteur de la base)
| Élément | Détail |
|---------|--------|
| Coûts | Swissquote : commissions par paliers + spread bid-ask + droit de timbre **CH 7.5 bps / étranger 15 bps** + **coût de change FX 20 bps** (cotation ≠ USD) + `min_trade_pct` 0.5% |

---

## 6. OUTPUT & persistance (Supabase)

| Table | Schéma | Contenu | Cadence |
|-------|--------|---------|---------|
| `portfolio_performance` | portfolio | NAV, return quotidien/cumulé, drawdown | recalculée chaque run |
| `portfolio_positions` | portfolio | poids détenus par date | recalculée |
| `portfolio_analytics` | portfolio | Sharpe, vol, max DD, return annualisé | recalculée |
| `backtest_runs` | portfolio | métadonnées du run | recalculée |

> Aucune table propriétaire : la stratégie est **sans état persistant propre** (le cache de
> rebalancement est en mémoire, reconstruit par la boucle chronologique → backtest == prod).
> Tables `portfolio_*` partagées avec les autres stratégies (différenciées par `strategy_name`,
> ex. `DynamicOpportunity_ACWI_rules_USD_B_Portfolio`).

---

## 7. Architecture & cohérence (points structurants)

1. **Closure à état** (`build_optimizer_fn`) : le panel ETF, les métadonnées et l'accès
   fondamental sont chargés **une fois** ; le cache de rebalancement vit dans la closure.
2. **Pas de look-ahead** : `as_of = prices.index[-1]` ; régime `rules` causal ; fondamentaux
   gated par `filing_date` ; exécution différée d'1 barre (défaut du moteur).
3. **Backtest == production** : la décision de rebal (ancre + flip) est reconstruite par la
   boucle chronologique, identique en backtest et en cron.
4. **Autonomie vs la base** : aucune modification du moteur partagé n'est requise — le
   rebalancement hybride est interne (pattern des strats à rebal dynamique). La base est
   épinglée par hash dans `requirements.txt`.
5. **Dégradation gracieuse** : ETF de régime manquants → poids renormalisés ; fondamentaux
   absents → momentum seul ; catégorie trop creuse → ignorée.

---

## 7ter. Chronologie d'exécution (ordre exact du code)

**SETUP (une fois, `RotationContext.build`)**
- **S1** — Lecture `params.yaml` + overrides d'environnement (`config_overrides`).
- **S2** — Chargement du **panel ETF de régime** (USD) tranchable PIT.
- **S3** — Chargement des **métadonnées titres** (`raw.tickers` : secteur/pays → catégorie).
- **S4** — Instanciation du **moteur de régime** + **pré-calcul de la série** (rules = causal).
- **S5** — Instanciation de l'**accès fondamental PIT** (si `selection_fundamental_weight>0`).

**BOUCLE — pour CHAQUE jour `as_of`** *(moteur de la base, cadence `B`)*
- **B0** — `filter_universe` : top 100/bourse par ADTV ; `hist_prices` tronqué à `as_of`.
- **B1** *(runner)* — **score de régime** lu à `as_of` ; `label` ; calcul de `flip` / `due`.
- **B2** — si **non due** → renvoie les **poids cachés** (fin de l'appel).
- **B3** — si **due** : **baromètre** (ÉTAPE 2) sur l'univers courant + score de régime.
- **B4** — **budgets** par catégorie (ÉTAPE 3, water-filling sous plafonds).
- **B5** — **composite fondamental PIT** des candidats (`financial_statements`, `filing_date≤as_of`).
- **B6** — **sélection** (ÉTAPE 4) : 10-20 lignes, budgets répartis, plafond par position.
- **B7** — mise à jour du cache (`weights`, `last_rebal=as_of`, `last_label`) ; log du rebal.

**FIN DE RUN** — `save_backtest_results` → `portfolio_performance/positions/analytics`
(même record que la production → une seule courbe continue).

---

## 8. Modes d'exécution & workflow

| `RUN_MODE` | Script | Rôle | Fréquence |
|-----------|--------|------|-----------|
| `backtest` | `run_backtest.py` | backtest d'amorçage + sauvegarde (`--dry-run`, `--no-costs`) | manuel, one-shot |
| `portfolio` | `run_daily_portfolio.py` | production : run + mise à jour positions/perf | cron quotidien |
| `track_record` | (base) | suivi de la perf du portefeuille réel | cron quotidien |

### Séquence de déploiement
```
1. python -m rotation.check_coverage  → valider ETF de régime + profondeur financial_statements
2. RUN_MODE=backtest (--dry-run)       → amorçage, vérifier Sharpe/DD
3. RUN_MODE=backtest                   → sauvegarde de la courbe de référence
4. Ablation (env)                      → REGIME_METHOD, SELECTION_FUNDAMENTAL_WEIGHT, seuils
5. RUN_MODE=portfolio                  → cron quotidien : prolonge la même courbe
```

### Lien avec la base
`requirements.txt` épingle `quant-portfolio-base` à un commit. Le workflow
`.github/workflows/update-base-hash.yml` (déclenché par dispatch `base-updated`) réécrit ce
hash automatiquement à chaque mise à jour de la base.

### Overrides d'environnement (`config_overrides.py`)
`UNIVERSE_NAME`, `EXCHANGES`, `PORTFOLIO_CURRENCY`, `SOURCE`, `DATA_ACCESS`,
`REBALANCE_FREQUENCY`, `START_DATE`, `STRATEGY_NAME`/`STRATEGY_VARIANT`, `REGIME_METHOD`,
`BASE_REBAL_DAYS`, `TARGET_POSITIONS_MIN/MAX`, `MAX_POSITION_WEIGHT`,
`SELECTION_FUNDAMENTAL_WEIGHT`, `REGIME_ON/OFF_THRESHOLD`.

---

## 9. Limites connues

| Sujet | État |
|-------|------|
| **Couverture fondamentale** | dépend de la profondeur de `raw.financial_statements` (`filing_date`) ; faible historique ⇒ étape 4 dégrade vers momentum seul. Vérifier via `rotation.check_coverage`. |
| **HMM / causal** | `hmm` : la série de régime est pré-calculée plein-échantillon → léger look-ahead sur le **timing des bascules** (préférer la cadence hebdo). `causal` = stub (repli `rules`) → phase 2. |
| **Couverture ETF de régime** | suppose les ETF SPDR/US syncés (`type='ETF'`) ; manquants → signaux renormalisés (régime moins riche). |
| **Granularité baromètre** | secteur × 4 régions (pragmatique) ; pays × secteur trop creux sur ACWI. |
| **Biais statique sectoriel** | `SECTOR_BIAS` posé à dire d'expert (offensif/défensif) ; non optimisé. |
| **Seuils régime / pondérations** | `on/off_threshold`, `regime_weights`, poids baromètre/sélection = heuristiques, non walk-forward (risque de sur-apprentissage si calibrés trop tôt). |
| **Turnover** | cadence `B` + recomputation à chaque ancre/flip → churn potentiel (atténué par `min_trade_pct` 0.5% + renvoi des poids cachés hors rebal). |
| **Long-only** | pas de short des secteurs en disgrâce ; en Risk Off on se contente du défensif. |
| **Portefeuille live** | valorisation/valeur via `fundamentals_snapshot` non encore branchée (uniquement backtest PIT pour l'instant). |

---

## 9bis. Conformité académique & institutionnelle

**Académique** — la chaîne reprend des régularités documentées :
| Élément | Référence (esprit) |
|---|---|
| Cycle Risk On/Off & rotation sectorielle | sector rotation / business-cycle investing (Stovall ; Conover et al.) |
| Spreads de crédit & courbe comme signaux de régime | term spread / credit spread predictors (Estrella & Hardouvelis ; Gilchrist & Zakrajšek) |
| Momentum cross-section (force relative des catégories) | Jegadeesh & Titman (1993) ; Moskowitz & Grinblatt (1999) |
| Régimes latents (option HMM) | Hamilton (1989) regime-switching |
| Qualité / croissance (composite fondamental) | quality factor (Asness, Frazzini & Pedersen) |

**Institutionnel** — bonnes pratiques de production :
- **Pas de look-ahead** : prix tronqués à `as_of` ; fondamentaux gated par `filing_date`
  (jamais `fundamentals_snapshot`) ; régime `rules` causal ; exécution différée d'1 barre.
- **Anti-survivorship** : `include_delisted: true` ; garde-fou mémoire stratifié par bourse.
- **Backtest == production** : décision de rebal reconstruite par la boucle chronologique.
- **Coûts réels conservateurs** (Swissquote : paliers, spread, droit de timbre CH/étranger,
  FX 20 bps, `min_trade` 0.5%).
- **Diversification** : plafonds par catégorie et par région ; filtre liquidité stratifié.
- **Reproductibilité** : moteurs déterministes (HMM seedé) ; aucune dépendance à un état caché
  non reconstructible.
- **Ablation** : régime / poids fondamental / seuils togglables par variable d'env.

---

## 10. Résumé en une page

```
ENTRÉE     : actions ACWI liquides (USD, filtre stratifié/bourse) + panel ETF (lecture régime)
ÉTAPE 1    : RÉGIME ∈[−1,+1] via ETF (momentum large, cyc/déf, courbe, crédit, or, USD, EM/DM),
             causal (rules) → label risk_on / risk_off / neutral
ÉTAPE 2    : BAROMÈTRE catégorie (secteur×région) → tilt = biais_statique×régime + momentum_z
ÉTAPE 3    : BUDGETS par catégorie ∝ tilt, water-filling sous plafonds catégorie/région
ÉTAPE 4    : SÉLECTION — composite fondamental PIT (qualité+croissance) + momentum → 10-20 lignes
             budget de catégorie réparti ; plafond 12%/position ; Σ=1
REBAL      : cadence moteur QUOTIDIENNE ; décision INTERNE = ancre hebdo (7j) OU bascule régime
RISQUE     : long-only, diversifié (plafonds région/catégorie), réactif aux bascules
PERSIST.   : portfolio_* (perf, 1 courbe) — aucune table propriétaire
ARCHI      : closure à état ; backtest == production ; AUTONOME vis-à-vis du moteur (pas de hook)
INFRA      : Railway (backtest one-shot + cron portfolio) | base épinglée par hash | données R2/EODHD
ANTI-BIAIS : as_of-tronqué · filing_date (PIT) · delisted inclus · exécution différée 1 barre
```
