# KID court — Dynamic Opportunity

> Synthèse en une page de la stratégie de **rotation Risk On / Risk Off**.
> Version détaillée : `STRATEGY_KID.md` / `STRATEGY_KID.html`.

## En une phrase
On lit la **phase de marché** (Risk On vs Risk Off) sur des ETF, on **penche le portefeuille**
vers les secteurs/régions favorisés par cette phase, puis on **choisit 10-20 actions** par leurs
fondamentaux et leur momentum. Actions only (ETF jamais détenus), univers ACWI, long-only.

## Le pipeline en 4 étapes
1. **Régime** (`regime.py`) — score ∈ [−1, +1] depuis les ETF (momentum large, ratio
   cycliques/défensifs, courbe, crédit, or, USD, EM/DM). +1 = Risk On, −1 = Risk Off.
2. **Baromètre** (`barometer.py`) — grille **secteur × région** ; chaque case reçoit un *tilt* =
   `biais_statique × régime + momentum_relatif`. Risk On → l'offensif s'allume ; Risk Off → le défensif.
3. **Budgets** (`allocation.py`) — les meilleures cases reçoivent un budget ∝ tilt, sous plafonds
   par catégorie (25 %) et par région (50 %), Σ = 1.
4. **Sélection** (`selection.py`) — dans chaque case, on classe les titres par
   **fondamental PIT (qualité + croissance) + momentum**, on garde 10-20 lignes (plafond 12 %/position).

## Rythme de rebalancement
Cadence moteur **quotidienne** ; la décision réelle est **interne** : rebalancement à l'**ancre
hebdomadaire** (7 j) **OU** dès qu'une **bascule de régime** Risk On↔Off est détectée (le jour même).
Entre deux décisions, le portefeuille dérive (le moteur gère).

## Données & anti-biais
- Prix actions ACWI (USD) + panel d'ETF (lecture du régime, jamais détenus).
- Secteur depuis `fundamentals_snapshot` ; fondamentaux PIT depuis `financial_statements`
  (`filing_date ≤ as_of`, JSONB income/balance).
- **Anti-look-ahead** : prix tronqués à `as_of`, fondamentaux gatés par `filing_date`, régime
  `rules` causal, exécution différée d'1 barre. **Anti-survivorship** : délistés inclus.
- **Garde-fou données** : un titre au momentum aberrant (|Δ| > 400 %, typique d'un split/devise
  non ajusté en small-cap EM) est **exclu** de la sélection.

## Paramètres clés
| Param | Val | Param | Val |
|---|---|---|---|
| seuils régime on/off | ±0.20 | nb positions | 10–20 |
| ancre rebal (`base_rebal_days`) | 7 j | plafond position | 12 % |
| catégories retenues | 8 | plafond catégorie / région | 25 % / 50 % |
| poids fondamental / momentum | 0.5 / 0.5 | momentum lookback | 126 j |

## Limites principales
- Le secteur doit être peuplé (`fundamentals_snapshot`) — sinon le baromètre dégénère.
- `hmm`/`causal` : léger look-ahead sur le timing des bascules → préférer `rules` (défaut).
- Cadence quotidienne en mode PIT = backtest long (≈ une fenêtre R2/jour).
- Long-only ; pas de short des secteurs en disgrâce.
