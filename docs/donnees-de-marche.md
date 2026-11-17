# Ce qu'il faut savoir sur les données de marché (P1, étape 1)

Notes de travail, pour le croisement SMA 50/200 sur BTC et S&P 500.

## 1. Clôture, clôture ajustée, et ce que Yahoo fait vraiment

- **Close** = dernier prix échangé de la séance. Chez Yahoo, il est **déjà corrigé des splits**,
  mais **pas des dividendes**. Ce n'est donc pas exactement « le prix affiché ce jour-là ».
- **Adj Close** = Close corrigé aussi des **dividendes**, par *back-adjustment* : on multiplie
  tout le passé par un facteur < 1 à chaque dividende. Le dernier prix est inchangé, le passé
  est abaissé.
- Conséquence 1 : un rendement calculé sur `adj_close` est un **rendement total** (dividende
  réinvesti). C'est ce qu'il faut pour un backtest d'actions ou d'ETF.
- Conséquence 2 : l'historique de `adj_close` **change à chaque nouveau dividende**. Deux
  téléchargements à deux dates différentes ne donnent pas les mêmes niveaux de prix (les
  rendements, eux, restent identiques). D'où le cache brut immuable avec date et sha256.
- Conséquence 3 : un **split** (ex. 4 pour 1) sur des prix bruts crée un faux -75 % en un jour.
  Le pipeline le détecte (avertissement `extreme_returns`).
- Règle : **rendements et signaux sur `adj_close`** ; `close` seulement quand il faut le
  prix réellement payé (taille d'ordre, prix limite).
- Le facteur `adj_close / close` doit être dans ]0, 1], croissant dans le temps, et égal à 1
  pour BTC et `^GSPC`. Le pipeline le vérifie.

## 2. Indice vs ETF : `^GSPC` n'est pas le S&P 500 que l'on peut acheter

| | `^GSPC` | `SPY` |
|---|---|---|
| Nature | indice de **prix** (calcul) | ETF coté (achetable) |
| Dividendes | **exclus** (~1,3 %/an aujourd'hui, 3-4 % dans les années 90) | réinvestis via `adj_close` |
| Frais | aucun | 0,0945 %/an (déjà dans le prix) |
| Historique | depuis 1927 (ici depuis 1990) | depuis le 29/01/1993 |

Sur 30 ans, l'écart de dividendes représente un facteur ~1,8 sur la richesse finale. Un
« buy & hold » sur `^GSPC` **sous-estime** donc le benchmark et flatte la stratégie de
croisement, qui est hors marché une partie du temps. **Décision : backtest sur `SPY`
(`adj_close`)**, `^GSPC` seulement comme référence longue.

Corollaire pour l'étape 3 : quand la stratégie est hors marché, elle détient du cash ; un
backtest honnête lui crédite le taux sans risque (T-bills), sinon on la pénalise à tort.

## 3. Bitcoin : `BTC-USD` chez Yahoo

- C'est un **cours agrégé** (multi-plateformes), pas une bourse. Il commence le **17/09/2014** ;
  l'histoire d'avant (Mt. Gox, 2010-2014) est illiquide et peu fiable.
- Une barre journalière = **00:00 → 24:00 UTC**. Pas de dividendes : `adj_close == close`.
- Le volume est agrégé et peu fiable ; on ne s'en sert pas.

## 4. Calendriers : 252 contre 365

- NYSE : ~**252 séances/an** (week-ends, ~9-10 jours fériés, fermetures exceptionnelles :
  11-14/09/2001, ouragan Sandy 29-30/10/2012, deuils nationaux 2018 et 2025). Le pipeline
  utilise le calendrier officiel `exchange_calendars` (XNYS) pour détecter les trous.
- Crypto : **365 barres/an**, aucun jour férié.
- **Annualisation** : volatilité × √252 pour SPY, × √365 pour BTC. Mélanger les deux fausse le
  Sharpe d'environ 20 %.
- **Piège du « 200 jours »** : une SMA 200 = 200 *barres*. Pour SPY c'est ~10 mois de
  calendrier, pour BTC ~6,5 mois. Le « 50/200 » n'a pas la même signification sur les deux
  actifs. Choix standard (retenu) : fenêtres en barres natives de chaque actif, en le disant
  dans le README.

## 5. Aligner deux actifs

- Pour comparer ou combiner : on **échantillonne BTC sur les séances NYSE** (`align_on_sessions`).
  Le rendement BTC vendredi → lundi inclut alors le week-end, ce qui est correct.
- **Jamais de forward-fill** de SPY sur les week-ends : cela fabrique des rendements nuls,
  baisse artificiellement la volatilité et gonfle le Sharpe.
- Décalage horaire : la clôture SPY est à 16:00 New York (20:00/21:00 UTC), celle de BTC à
  00:00 UTC. Même étiquette de date, instants différents. Sans conséquence pour des stratégies
  mono-actif, mais un signal BTC utilisé pour trader SPY le même jour serait une anticipation.

## 6. Dates et fuseaux

- Index stocké en **UTC à minuit = date de séance**. Yahoo renvoie SPY en heure de New York ;
  on lit la date **locale** puis on l'étiquette en UTC (convertir naïvement peut décaler d'un
  jour pour une bourse asiatique).
- La barre du jour en cours n'est pas terminée : le pipeline **ignore toute barre ≥ aujourd'hui
  (UTC)**.

## 7. Biais à garder en tête

- **Anticipation (look-ahead)** : signal calculé avec la clôture de t, exécuté au plus tôt en
  t+1 (`shift(1)`), testé à l'étape 4. Subtilité : `adj_close` utilise des dividendes
  postérieurs à t pour corriger le niveau en t. Les rendements n'en sont pas affectés, mais une
  règle sur un **niveau** de prix (« acheter sous 100 $ ») le serait. Le croisement 50/200
  compare deux moyennes du même actif : effet négligeable.
- **Survivant** : choisir BTC en 2026, c'est choisir *la* crypto qui a survécu parmi des milliers
  de projets morts. Même logique pour le S&P 500 (le marché américain a été le grand gagnant du
  siècle). Le résultat dira « sur ces actifs », pas « en général ».
- **Data snooping** : le 50/200 est célèbre précisément parce qu'il a bien marché par le passé.
  Les paramètres ne seront pas optimisés sur toute la période ; test de sensibilité à l'étape 4.
- **Source non officielle** : Yahoo peut réviser ou corriger son historique. Le cache brut
  versionné (sha256) rend chaque résultat reproductible.
