# FestiPlan

API FastAPI de gestion d'un festival metal fictif : festivals, scènes, artistes, concerts, publication du planning et déclaration d'incidents.

Le projet est parti d'un dépôt volontairement imparfait (règles métier dispersées, routes qui accédaient directement à la base, notifications couplées aux opérations). Il a été refactorisé en **architecture hexagonale** avec une approche **DDD** : les règles métier sont dans un domaine indépendant de FastAPI et de SQLAlchemy, et les trois défauts connus du dépôt initial sont corrigés et testés.

## Installation (Python 3.11+)

Depuis le dossier `festiplan` :

```bash
python -m venv .venv
# Windows PowerShell : .venv\Scripts\Activate.ps1
# Git Bash : source .venv/Scripts/activate
# macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
```

Documentation interactive : http://127.0.0.1:8000/docs

Par défaut, SQLite crée `festiplan.db` dans le dossier courant. Pour changer la configuration, copier `.env.example` vers `.env` :

| Variable | Rôle |
|---|---|
| `FESTIPLAN_DATABASE_URL` | URL de la base (SQLite par défaut) |
| `FESTIPLAN_FAIL_NOTIFICATIONS` | `true` pour simuler une panne du service de notification |
| `FESTIPLAN_APP_NAME` | Nom affiché dans la documentation |

## Données de démonstration

`python -m app.seed` charge le festival fictif **Hellforge Open Air** (18 au 20 juin 2027) : 4 scènes (Mainstage, Warzone, Valley, Temple), 12 artistes et 14 concerts. Les groupes, horaires et capacités sont inventés.

## Architecture

```text
app/
├── domain/          Cœur métier : entités, objets-valeurs, règles (aucun import FastAPI/SQLAlchemy)
├── application/     Cas d'utilisation + ports (ports.py)
├── api/             Adaptateurs entrants : routes FastAPI, traduction des erreurs en codes HTTP
├── infrastructure/  Adaptateurs sortants (SQLAlchemy, e-mail) + composition (wiring.py)
├── models.py        Tables SQLAlchemy
└── schemas.py       Format des requêtes et réponses (Pydantic)
```

Les dépendances vont toujours vers le cœur : le domaine ne dépend de rien, les cas d'utilisation ne dépendent que du domaine et des ports, et seul `infrastructure/wiring.py` connaît les implémentations concrètes.

Pour le détail, voir le dossier [`festiplan/livrables/`](festiplan/livrables/) :

- [`Note architecture.md`](festiplan/livrables/Note%20architecture.md) : choix d'architecture, ports et adaptateurs, limites et compromis ;
- [`diagrammes.md`](festiplan/livrables/diagrammes.md) : diagramme de composants et diagramme de séquence ;
- [`modele-domaine.md`](festiplan/livrables/modele-domaine.md) : entités, objets-valeurs, agrégats et règles R1 à R10 ;
- [`diagnostic-architecture.md`](festiplan/livrables/diagnostic-architecture.md) : analyse du dépôt initial.

Le déroulé de la refactorisation et de la correction des défauts est dans [`REFACTORING.md`](festiplan/livrables/REFACTORING.md).

## Principales routes

| Ressource | Routes |
|---|---|
| Festivals | `GET /festivals`, `POST /festivals`, `POST /festivals/{id}/publish`, `POST /festivals/{id}/unpublish` |
| Scènes | `GET /stages?festival_id=`, `POST /stages` |
| Artistes | `GET /artists`, `POST /artists` |
| Concerts | `GET /concerts?festival_id=`, `GET /concerts/{id}`, `POST /concerts`, `PATCH /concerts/{id}/reschedule`, `POST /concerts/{id}/cancel` |
| Incidents | `GET /incidents?concert_id=`, `POST /incidents` |
| Notifications | `GET /notifications/pending`, `POST /notifications/retry` |

Codes d'erreur : `400` donnée refusée par une règle métier, `404` objet introuvable, `409` conflit avec l'état actuel (créneau occupé, planning publié), `422` requête mal formée.

## Comportements métier à connaître

- **Conflits** : un concert ne peut pas chevaucher un autre concert sur la même scène, ni faire jouer le même artiste deux fois en même temps. Les concerts annulés ne bloquent pas de créneau.
- **Planning publié** : une fois publié, le planning est figé. Programmer, déplacer ou annuler un concert renvoie `409`. Pour le modifier, il faut le dépublier (`POST /festivals/{id}/unpublish`), faire les changements, puis le republier. La publication est refusée si le planning contient un conflit.
- **Notifications** : une panne du service de notification n'annule jamais une modification enregistrée. La réponse reste `200` et indique `"notification": {"status": "pending_retry"}`. La notification est conservée et peut être renvoyée avec `POST /notifications/retry`.

## Tests

Depuis le dossier `festiplan`, avec l'environnement virtuel activé :

```bash
python -m pytest -q                                      # toute la suite (89 tests)

python -m pytest -q tests/test_domain.py                 # domaine (sans FastAPI ni base)
python -m pytest -q tests/test_schedule_use_case.py tests/test_reschedule_use_case.py   # cas d'utilisation
python -m pytest -q tests/test_step5_defects.py          # non-régression des 3 défauts
```

Les tests HTTP utilisent une base SQLite temporaire : ils ne touchent pas à `festiplan.db`. La stratégie de tests est décrite dans [`REFACTORING.md`](festiplan/livrables/REFACTORING.md) (étape 6).

## Défauts du dépôt initial (corrigés)

1. **Chevauchement de concerts** : le déplacement ne vérifiait pas les conflits. Il est désormais refusé avec `409`.
2. **Notification en échec** : l'API répondait `500` alors que le déplacement était enregistré. Elle répond maintenant `200` en indiquant l'état de la notification.
3. **Planning publié** : un concert pouvait être déplacé après publication. Le planning publié est maintenant figé, et doit être dépublié pour être modifié.

Pour vérifier : `FESTIPLAN_FAIL_NOTIFICATIONS=true` simule la panne du défaut 2, et `tests/test_step5_defects.py` couvre les trois scénarios.

Tous les diagrammes et schémas s'affichent directement sur GitHub.