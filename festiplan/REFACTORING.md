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
La notification est un effet secondaire : si elle échoue, l'erreur est journalisée et le déplacement reste valide.

### 5. Ports et adaptateurs
- Ports (`app/application/ports.py`) : `ConcertRepository`, `FestivalRepository`, `Notifier`.
- Adaptateurs (`app/infrastructure/`) : `SqlAlchemyConcertRepository`, `SqlAlchemyFestivalRepository`, `EmailNotifier`.

### 6. Contrôleur HTTP — `app/api/concerts.py`
Le contrôleur ne fait plus de requête SQL : il construit la commande, appelle le cas d'utilisation et traduit les erreurs métier en codes HTTP. Le câblage est fait dans `get_reschedule_concert` (dépendance FastAPI, remplaçable dans les tests).

### 7. Vérification
- `tests/test_reschedule_use_case.py` : tests unitaires avec faux en mémoire (aucune base).
- `pytest` : 25 tests verts. API vérifiée manuellement sur les données de `app.seed`.

### Choix à discuter
- 409 pour un conflit ou un planning figé, 400 pour une donnée invalide.
- La notification « au mieux » est la solution simple ; une boîte d'envoi (outbox) garantirait l'envoi.
- Le changement d'équipement n'est pas vérifié au déplacement : la scène ne change pas, donc les équipements non plus.

## Prochaines fonctionnalités (étape 8)
1. **Créer un concert** : réutiliser `TimeSlot` et la détection de conflits du domaine, ajouter la règle des équipements, supprimer `SchedulingService._check_conflicts`.
2. **Annuler un concert** : `Concert.cancel()` + cas d'utilisation `CancelConcert`.
3. **Publier un festival** : vérifier qu'il n'y a aucun conflit avant publication, même gestion de la notification.
4. **Consulter un concert / déclarer un incident** : retirer les accès SQLAlchemy directs des contrôleurs.
