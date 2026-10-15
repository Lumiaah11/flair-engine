# Flair, moteur de collecte

Chaque nuit, ce dépôt lit les offres publiées par une centaine d'entreprises et quelques agrégateurs,
garde les postes de stratégie en France et à l'international (et les VIE), leur donne un score automatique, puis enregistre le résultat dans `data/`.
Le matin, Claude note ces offres plus finement et remplit la page privée Flair.

## Ce que contient le dépôt

- `engine/` : le code de collecte et de tri.
- `config/entreprises.json` : les entreprises suivies et leur logiciel de recrutement. Ajouter une ligne suffit pour suivre une nouvelle entreprise.
- `config/agregateurs.json` : VIE Business France, The Muse, Adzuna, Jooble.
- `config/reglages.json` : seuil de score et durée de conservation.
- `data/offres.json` : toutes les offres retenues et encore ouvertes.
- `data/nouvelles.json` : les offres vues pour la première fois lors de la dernière collecte.
- `data/stats.json` : le bilan de chaque source (lues, retenues, erreurs).
- `data/rejets.json` : un échantillon des offres écartées, avec la raison.

## Clés facultatives

Adzuna, Jooble et France Travail demandent une clé gratuite. Sans clé, ces sources sont simplement ignorées.
Pour les ajouter : Settings, puis Secrets and variables, puis Actions, et créer `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_KEY`,
`FT_CLIENT_ID` et `FT_CLIENT_SECRET`. La France peut être retirée avec `"inclure_france": false` dans `config/reglages.json`.

## Lancer une collecte à la main

Onglet Actions, workflow « Collecte Flair », bouton « Run workflow ».

## Ce que le moteur ne fait jamais

Il ne postule pas, ne contacte personne et ne lit aucune donnée personnelle. Il ne lit que des offres publiées publiquement.
