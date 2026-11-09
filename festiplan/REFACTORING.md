# Étape 4 — Refactorisation progressive

## Fonctionnalité 1 : déplacer un concert (`PATCH /concerts/{id}/reschedule`)

### 1–2. Comportement existant et tests
Avant de toucher au code, `tests/test_reschedule_api.py` a été écrit :

| Test | Code legacy | Après refacto |
|---|---|---|
| Déplacement sur créneau libre → 200 et persistance | ✅ | ✅ |
| Concert inconnu → 404 | ✅ | ✅ |
| Fin avant début → 400 | ✅ | ✅ |
| Scène déjà occupée → 409 (scénario 1) | ❌ 200 | ✅ |
| Artiste déjà programmé ailleurs → 409 | ❌ 200 | ✅ |
| Hors dates du festival → 400 | ❌ 200 | ✅ |
| Concert annulé → 409 | ❌ 200 | ✅ |
| Festival publié → 409 (scénario 3) | ❌ 200 | ✅ |
| Panne de notification → 200, déplacement conservé (scénario 2) | ❌ 500 | ✅ |

Résultat legacy : 4 passés, 6 échoués. Après : tous passent.

### 3. Règles métier isolées — `app/domain/scheduling.py`
- `TimeSlot` : un créneau valide (fin > début), `overlaps()`, `is_within()`.
- `Concert.reschedule(new_slot, festival, others)` : toutes les règles du déplacement au même endroit.
- Erreurs métier explicites (`SchedulingConflict`, `OutsideFestivalPeriod`, …).
- Aucun import FastAPI / SQLAlchemy / config.

### 4. Cas d'utilisation — `app/application/reschedule_concert.py`
`RescheduleConcert.execute(command)` : charge, applique la règle du domaine, sauvegarde, notifie.
La notification est un effet secondaire : si elle échoue, le déplacement reste valide. Dans cette première version, l'échec était seulement journalisé ; depuis l'étape 5, la notification est mise en file d'attente (voir défaut 2).

### 5. Ports et adaptateurs
- Ports (`app/application/ports.py`) : `ConcertRepository`, `FestivalRepository`, `Notifier`.
- Adaptateurs (`app/infrastructure/`) : `SqlAlchemyConcertRepository`, `SqlAlchemyFestivalRepository`, `EmailNotifier`.

### 6. Contrôleur HTTP — `app/api/concerts.py`
Le contrôleur ne fait plus de requête SQL : il construit la commande, appelle le cas d'utilisation et traduit les erreurs métier en codes HTTP. Le câblage (`get_reschedule_concert`, dépendance FastAPI remplaçable dans les tests) a ensuite été regroupé avec celui des autres cas d'utilisation dans `app/infrastructure/wiring.py`.

### 7. Vérification
- `tests/test_reschedule_use_case.py` : tests unitaires avec faux en mémoire (aucune base).
- `pytest` : 71 tests verts lors de la dernière vérification.

### Choix retenus
- 409 pour un conflit ou un planning figé, 400 pour une donnée invalide.
- Notification : d'abord « au mieux » (journalisation), puis remplacée à l'étape 5 par une file d'attente avec renvoi à la demande (voir défaut 2).
- Le changement d'équipement n'est pas vérifié au déplacement : la scène ne change pas, donc les équipements non plus.

## Fonctionnalités ajoutées après la première refactorisation

Les opérations suivantes ont également été déplacées derrière des cas d'utilisation et des ports/adaptateurs :

- créer des concerts, artistes, scènes et festivals ;
- annuler un concert ;
- publier et dépublier un festival, avec vérification des conflits avant publication ;
- consulter un concert ou le planning, et déclarer ou consulter des incidents ;
- mettre en attente et renvoyer les notifications échouées.

Les tests HTTP correspondants se trouvent notamment dans `tests/test_refactored_api.py`.

---

# Étape 5 — Correction des trois défauts initiaux

Tests d'acceptation : `tests/test_step5_defects.py` (niveau HTTP), complétés par `tests/test_refactored_api.py`.
Tests unitaires : `tests/test_reschedule_use_case.py` (faux en mémoire, sans base).
Lors de la dernière vérification : **71 tests passent**.

## Défaut 1 — Conflits de programmation

**Règle :** un déplacement est refusé (`409`) si le nouveau créneau chevauche un autre concert non annulé
du même festival **sur la même scène**, ou **avec le même artiste** (quelle que soit la scène).
Les créneaux bout à bout (16h-17h puis 17h-18h) ne sont pas en conflit ; un concert peut chevaucher son propre ancien créneau.

**Où :** `Concert._check_slot()` dans `app/domain/scheduling.py`, appelé par `Concert.reschedule()` (déplacement) et `Concert.schedule()` (programmation) : la règle est la même pour les deux opérations.

| Test | Attendu |
|---|---|
| Chevauchement sur la même scène | 409 « la scène est déjà occupée », rien n'est modifié |
| Artiste sur deux scènes en même temps | 409 « l'artiste est déjà programmé », rien n'est modifié |
| Déplacement valide | 200, nouveau créneau persisté |
| Créneaux adjacents / chevauchement de son propre créneau | 200 |

## Défaut 2 — Notification en échec

**Problème :** le déplacement était enregistré (`commit`) puis l'envoi échouait → `500`, alors que la modification était faite.

**Décision :** l'opération métier est la source de vérité, la notification est un effet secondaire.
- Si la modification est enregistrée, la réponse est **toujours `200`** et contient un champ explicite :
  - `"notification": {"status": "sent"}` si l'envoi a réussi ;
  - `"notification": {"status": "pending_retry", "detail": "..."}` s'il a échoué.
- Une notification en échec n'est pas perdue : elle est stockée dans la table `pending_notifications`.
- `GET /notifications/pending` liste la file ; `POST /notifications/retry` renvoie les notifications
  (supprimées si l'envoi réussit, compteur `attempts` incrémenté sinon).
- Un déplacement refusé n'envoie aucune notification.

**Pourquoi c'est proportionné :** pas de file de messages ni de tâche de fond (non demandées), mais aucune
information perdue et une réponse HTTP qui dit la vérité. Le renvoi pourrait plus tard être appelé par une tâche planifiée.
La même logique (`notify_or_queue`) est appliquée à la publication, qui avait le même défaut.

**Où :** `app/application/notifications.py`, port `PendingNotificationStore`, adaptateur `SqlAlchemyPendingNotificationStore`.

## Défaut 3 — Planning publié

**État métier :** `FestivalStatus` = `preparation` ↔ `published`, porté par l'entité `Festival` du domaine.

| Opération | `preparation` | `published` |
|---|---|---|
| Publier (`POST /festivals/{id}/publish`) | ✅ → `published` (notifie) si aucun conflit, sinon ❌ 409 (R8) | ❌ 409 |
| Dépublier (`POST /festivals/{id}/unpublish`) | ❌ 409 | ✅ → `preparation` |
| Déplacer un concert | ✅ | ❌ 409 |
| Ajouter un concert | ✅ | ❌ 409 |
| Annuler un concert | ✅ | ❌ 409 |

**Règle retenue :** refus + dépublication explicite. Un planning publié est figé ; pour le modifier,
l'organisateur le dépublie, fait ses changements, puis le republie, ce qui renvoie une notification.
On a choisi cette solution plutôt qu'une « procédure spéciale » parce qu'elle est simple, visible dans l'API,
et qu'elle évite toute modification silencieuse d'un planning déjà communiqué au public.

**L'annulation suit la même règle :** elle est refusée tant que le planning est publié. L'organisateur doit
d'abord dépublier le festival ; il peut ensuite annuler le concert, puis republier le planning.

**Republication (R8) :** avant de publier, tous les concerts non annulés sont revérifiés (même scène, même
artiste, dates du festival). S'il reste un problème, la publication est refusée (409) et le message liste
les concerts concernés. Si elle réussit, une notification « planning publié » est envoyée.

**Où :**
- domaine (`app/domain/scheduling.py`) : `Festival.publish(concerts)` (avec `schedule_problems()` pour R8),
  `Festival.unpublish()`, `Festival.ensure_schedule_editable()`, appelé par `Concert.schedule()`,
  `Concert.reschedule()` et `Concert.cancel()` ;
- cas d'utilisation : `PublishFestival` / `UnpublishFestival` (`app/application/festival_publication.py`),
  `CancelConcert` (`app/application/cancel_concert.py`).

**Limite connue :** la détection des chevauchements existe à deux endroits, `Concert._check_slot()`
(programmation, déplacement) et `schedule_problems()` (publication). Les deux appliquent la même règle,
mais une évolution devra être reportée dans les deux.

## Code supprimé
Tout l'ancien code a été remplacé par les cas d'utilisation et les adaptateurs :
`app/services/` (dont `PublicationService`, `NotificationService` et `SchedulingService`),
`app/repositories/` et `app/utils/date_helpers.py`.