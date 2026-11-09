# Note d'architecture — FestiPlan

## 1. Point de départ

Le dépôt initial avait déjà des dossiers `api/`, `services/` et `repositories/`, mais leurs rôles se chevauchaient :

- les règles métier étaient dispersées entre les routes, les services et les schémas Pydantic ;
- certaines routes faisaient elles-mêmes des requêtes SQLAlchemy, par exemple pour déplacer un concert ou déclarer un incident ;
- les services dépendaient directement de SQLAlchemy et de l'envoi d'e-mail, ce qui les rendait difficiles à tester seuls.

Conséquence : une règle appliquée à la création d'un concert était oubliée au déplacement. C'est l'origine des trois défauts (chevauchements non détectés, erreur 500 après un déplacement enregistré, planning publié modifiable).

## 2. Les couches et leurs responsabilités

| Notion hexagonale | Emplacement | Responsabilité |
|---|---|---|
| Domaine | `app/domain/` | Entités, objets-valeurs et règles métier. Ne dépend de rien d'autre. |
| Cas d'utilisation | `app/application/` | Orchestrer une opération : charger les objets via les ports, déléguer les règles au domaine, sauvegarder, notifier. |
| Ports | `app/application/ports.py` | Contrats dont le cœur a besoin (interfaces `Protocol`). |
| Adaptateurs entrants | `app/api/` | Routes FastAPI : valider le format (Pydantic), construire la commande, appeler le cas d'utilisation, traduire les erreurs métier en codes HTTP (`errors.py`) et les objets en JSON (`presenters.py`). |
| Adaptateurs sortants | `app/infrastructure/` | Implémentations des ports : repositories SQLAlchemy et envoi d'e-mail. |
| Composition | `app/infrastructure/wiring.py` | Seul module qui connaît à la fois les cas d'utilisation et les classes concrètes. Il les assemble et les fournit aux routes via `Depends`. |

**Règle de dépendance** : toutes les dépendances vont vers le cœur. Le domaine n'importe ni FastAPI, ni SQLAlchemy, ni la configuration, et les cas d'utilisation n'importent pas l'infrastructure. Les tests du domaine et des cas d'utilisation s'exécutent d'ailleurs sans charger FastAPI ni la base.

Les dossiers ne s'appellent pas `ports/` et `adapters/` : nous avons gardé les noms choisis lors de la première refactorisation (`api/`, `infrastructure/`, `ports.py`). Le rôle de chaque partie est celui du tableau ci-dessus.

## 3. Ports et adaptateurs

| Port | Adaptateur | Utilité |
|---|---|---|
| `ConcertRepository` | `SqlAlchemyConcertRepository` | Charger les concerts d'un festival pour vérifier les conflits, enregistrer un concert. |
| `FestivalRepository` | `SqlAlchemyFestivalRepository` | Charger un festival (période, statut) et enregistrer sa publication. |
| `ArtistRepository` | `SqlAlchemyArtistRepository` | Retrouver un artiste et ses besoins techniques. |
| `StageRepository` | `SqlAlchemyStageRepository` | Retrouver une scène, son festival et ses équipements. |
| `IncidentRepository` | `SqlAlchemyIncidentRepository` | Enregistrer et lister les incidents. |
| `Notifier` | `EmailNotifier` | Envoyer une notification sans que le cœur sache qu'il s'agit d'un e-mail. |
| `PendingNotificationStore` | `SqlAlchemyPendingNotificationStore` | Conserver les notifications en échec pour les renvoyer. |

Les repositories convertissent les lignes SQLAlchemy (`models.py`) en objets du domaine : le cœur ne manipule jamais de modèle de base de données. Dans les tests, ces ports sont remplacés par des faux en mémoire.

## 4. Modèle du domaine

Le détail est dans [`modele-domaine.md`](modele-domaine.md). En résumé :

- **Entités** : `Festival`, `Concert`, `Stage`, `Artist`, `Incident`.
- **Objets-valeurs** : `TimeSlot` (créneau, et période du festival), `EquipmentSet`, `Capacity`, `IncidentDescription`. Ils refusent une valeur invalide dès leur création (R1, R9, R10).
- **Agrégats** : le `Concert` porte les règles de programmation (`schedule`, `reschedule`, `cancel`) et reçoit le festival et les autres concerts pour vérifier R2, R3, R5 et R6. Le `Festival` porte le cycle de vie du planning (`publish`, `unpublish`, `ensure_schedule_editable`) et vérifie R7 et R8.
- **Règle de placement** : le domaine vérifie tout ce qui ne dépend que des données qu'il reçoit, et le cas d'utilisation vérifie ce qui demande d'interroger un repository (l'existence d'un objet, R4). Pydantic ne fait plus que valider le format des requêtes.

## 5. Correction des trois défauts

| Défaut | Correction | Où |
|---|---|---|
| 1. Chevauchements | Le déplacement passe par les mêmes vérifications que la programmation (même scène, même artiste, période du festival). | `Concert._check_slot()` |
| 2. Notification en échec | La notification est envoyée après l'enregistrement. En cas d'échec, elle est mise en file d'attente et la réponse reste `200`, avec `"notification": {"status": "pending_retry"}`. | `application/notifications.py` |
| 3. Planning publié | État `preparation` / `published`. Un planning publié est figé : programmer, déplacer et annuler sont refusés (`409`). Pour le modifier, on le dépublie, puis on le republie, ce qui revérifie tout le planning (R8). | `Festival` |

Le détail et les tests associés sont dans [`REFACTORING.md`](../REFACTORING.md) (étape 5), et le déroulé d'un déplacement dans le diagramme de séquence.

### Défaut 3 : les options envisagées

Le sujet laisse le choix du comportement à adopter quand on veut modifier un planning déjà publié. Nous avons comparé trois options :

| Option | Principe | Avantage | Inconvénient |
|---|---|---|---|
| 1. Refus pur | Un planning publié ne peut plus jamais être modifié. | La plus simple. | Un festival est bloqué au moindre imprévu (artiste absent, scène en panne). |
| **2. Dépublication préalable** (retenue) | Toute modification du planning est refusée tant qu'il est publié (déclarer un incident reste possible). L'organisateur le dépublie, fait ses changements, puis le republie. | Aucune règle de modification particulière : on réutilise les opérations ordinaires avec toutes leurs vérifications, et la republication revérifie tout le planning (R8). | Le planning n'est plus publié pendant la correction, et rien ne garde la raison du changement. |
| 3. Modification exceptionnelle avec motif | Le planning reste publié, et une opération dédiée permet de le modifier en donnant un motif obligatoire, tracé et annoncé au public. | La plus proche de la réalité d'un festival. | Une nouvelle opération à concevoir et à tester, avec le stockage du motif. |

Nous avons retenu l'**option 2** : elle évite le blocage de l'option 1 pour peu de code en plus (une opération `unpublish`), et elle reste explicite dans l'API. Pour qu'elle soit sûre, deux règles l'accompagnent : programmer, déplacer **et annuler** un concert sont tous refusés sur un planning publié, sinon on pourrait le modifier sans le dépublier ; et la publication est refusée si le planning contient un conflit (R8). L'option 3 reste l'évolution naturelle si l'on a besoin de corriger un planning sans le retirer du public.

## 6. Stratégie de tests

| Niveau | Fichiers | Ce qui est vérifié |
|---|---|---|
| Domaine | `test_domain.py` | Créneaux, chevauchements, invariants, transitions de publication. Sans FastAPI ni base. |
| Cas d'utilisation | `test_schedule_use_case.py`, `test_reschedule_use_case.py` | Orchestration, erreurs et appels aux ports, avec des faux en mémoire. |
| Adaptateurs | `test_refactored_api.py`, `test_reschedule_api.py`, `test_*_api.py` | Routes HTTP et persistance, sur une base SQLite temporaire. |
| Non-régression | `test_step5_defects.py` | Les trois défauts, avec des tests qui échouaient sur le code initial. |

Nous n'avons pas cherché à tester chaque ligne, mais les règles métier, les refus et les comportements qui doivent rester garantis. La suite compte 89 tests.

## 7. Limites et compromis

**Choix de modélisation**

- **Agrégat `Concert` plutôt que `Festival`.** Un festival qui contiendrait tous ses concerts protégerait mieux R2 et R3, mais obligerait à charger et enregistrer tout le planning pour modifier un concert. Nous avons gardé un agrégat par concert, plus proche de la base existante. Contrepartie : les conflits ne sont détectés que si le cas d'utilisation fournit bien la liste complète des autres concerts.
- **Pas d'événements de domaine.** Les cas d'utilisation appellent directement le port `Notifier` après l'enregistrement. C'est suffisant ici, mais un nouvel effet secondaire devra être ajouté à la main dans chaque cas d'utilisation concerné.
- **La règle des conflits existe à deux endroits** : `Concert._check_slot()` pour programmer et déplacer, `schedule_problems()` pour la publication (R8). Les deux appliquent la même règle, mais une évolution devra être reportée dans les deux. `schedule_problems()` liste tous les problèmes du planning, ce que `_check_slot()` ne fait pas.

**Choix métier**

- **Planning publié : dépublication préalable (option 2, voir section 5).** Le planning n'est plus publié pendant la correction, et rien ne garde la raison du changement. Une modification exceptionnelle avec motif obligatoire (option 3) serait plus adaptée en production.
- **Conflits limités à un festival.** Un artiste programmé au même moment dans deux festivals différents n'est pas détecté.

**Choix techniques**

- **Notifications.** L'envoi est synchrone, et le renvoi des notifications en attente se fait à la demande (`POST /notifications/retry`), pas automatiquement. L'enregistrement de la modification et la mise en file d'attente sont deux transactions séparées : un arrêt brutal entre les deux ferait perdre la notification, mais jamais la modification.
- **Pas de contrôle de concurrence.** Deux déplacements simultanés sur un même festival pourraient chacun passer la vérification des conflits. Un numéro de version ou un verrou serait nécessaire avec plusieurs utilisateurs.
- **Codes HTTP modifiés.** Pour être cohérents avec le déplacement, un conflit à la création d'un concert renvoie maintenant `409` au lieu de `400`, et une référence introuvable renvoie `404` au lieu de `400`.
- **Lectures simples.** Les listes (festivals, artistes, scènes, incidents) passent par de petits cas d'utilisation qui ne font qu'appeler le repository. C'est cohérent avec l'architecture, mais ces classes n'apportent pas de règle.

**Démarche**

- La fin de la refactorisation (création, annulation, publication et fonctionnalités restantes) a été livrée en un seul commit, alors que le déplacement avait été refactorisé progressivement. L'historique Git montre donc moins bien la démarche pour cette partie.
- Les tests sont rangés à plat dans `tests/`, et certains tests du déplacement existent à la fois dans `test_reschedule_api.py` (étape 4) et `test_step5_defects.py` (étape 5).