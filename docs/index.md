# quant-ma-crossover

**Question :** le croisement de moyennes mobiles 50/200 jours (« golden cross / death cross »)
bat-il le simple *buy & hold* sur le **Bitcoin** et le **S&P 500**, une fois les frais inclus ?

Ce site documente la démarche pas à pas : données, concepts, backtest, pièges et résultats.
Le code est sur [GitHub](https://github.com/Djewiet/quant-ma-crossover).

## Statut du projet

| Étape | Contenu | Statut |
|---|---|---|
| 1. Données | structure du repo, téléchargement BTC + S&P 500, cache immuable, validation | ✅ terminé |
| 2. Concepts | rendements, volatilité, moyennes mobiles | ⬜ à faire |
| 3. Backtest | signal (exécuté en t+1), positions, equity curve vs buy & hold | ⬜ à faire |
| 4. Pièges | frais, slippage, test anti-lookahead, sensibilité aux paramètres, hors échantillon | ⬜ à faire |
| 5. Présentation | résultats, figures, tag `v1.0.0` | ⬜ à faire |

## La stratégie en une formule

Avec \(P_t\) le prix ajusté de clôture et \(\text{SMA}_n(t) = \frac{1}{n}\sum_{k=0}^{n-1} P_{t-k}\) :

\[
s_t = \mathbb{1}\left[\text{SMA}_{50}(t) > \text{SMA}_{200}(t)\right],
\qquad
r^{\text{strat}}_{t+1} = s_t \, r_{t+1} - c \,\lvert s_t - s_{t-1} \rvert
\]

Le signal \(s_t\) est calculé avec la clôture de \(t\) et appliqué au rendement de \(t+1\) :
aucune information future n'entre dans la décision. \(c\) est le coût par changement de
position (frais + slippage).

!!! warning "Limites"
    Projet de recherche et d'apprentissage, pas un conseil en investissement. Les résultats
    dépendront de la période étudiée, des coûts retenus et de données Yahoo non officielles.
    Choisir BTC et le S&P 500 aujourd'hui est déjà un biais du survivant.

## Données

| Actif | Ticker | Calendrier | Prix utilisé |
|---|---|---|---|
| Bitcoin | `BTC-USD` | 24/7, 365 barres/an (jours UTC) | `adj_close` (= `close`) |
| ETF S&P 500 | `SPY` | NYSE, ~252 séances/an | `adj_close` (dividendes réinvestis) |
| Indice S&P 500 | `^GSPC` | NYSE | `close` (prix seul, référence) |

Tout ce qu'il faut savoir sur ces données (ajustements, calendriers, fuseaux, biais) :
[Données de marché](donnees-de-marche.md).

## Reproduire

```bash
uv sync
uv run ma-crossover fetch          # télécharge une fois, puis lit le cache
uv run ruff check . && uv run mypy && uv run pytest
```

Pour consulter cette documentation en local :

```bash
uv sync --group docs
uv run mkdocs serve                # http://127.0.0.1:8000
```
