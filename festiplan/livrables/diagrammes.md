# Diagrammes d'architecture

## 1. Diagramme de composants

```mermaid
flowchart TB
    client(["Client HTTP<br/>(Swagger, front, tests)"])

    subgraph ENTREE["Adaptateurs d'entrée — app/api/ (+ app/schemas.py)"]
        routes["Routeurs FastAPI<br/>concerts.py · festivals.py · artists.py<br/>stages.py · incidents.py · notifications.py"]
        schemas["app/schemas.py<br/>DTO Pydantic"]
        presenters["presenters.py<br/>domaine → JSON"]
        errors["errors.py<br/>erreur métier → 404 / 409 / 400"]
    end

    wiring["Composition — infrastructure/wiring.py<br/>get_reschedule_concert, get_publish_festival, ...<br/>assemble cas d'utilisation + adaptateurs (Depends)"]

    subgraph COEUR["Cœur applicatif — aucun import FastAPI / SQLAlchemy"]
        subgraph APP["Cas d'utilisation — app/application/"]
            uc_concert["ScheduleConcert · RescheduleConcert<br/>CancelConcert · GetConcert · GetFestivalSchedule"]
            uc_fest["PublishFestival · UnpublishFestival<br/>CreateFestival · ListFestivals<br/>CreateArtist · CreateStage · ReportIncident ..."]
            uc_notif["notifications.py<br/>notify_or_queue · RetryPendingNotifications"]
        end
        subgraph PORTS["Ports — app/application/ports.py (Protocol)"]
            p_repos[["ConcertRepository · FestivalRepository<br/>ArtistRepository · StageRepository<br/>IncidentRepository"]]
            p_pending[["PendingNotificationStore"]]
            p_notifier[["Notifier"]]
        end
        subgraph DOM["Domaine — app/domain/"]
            d_sched["scheduling.py<br/>Festival · FestivalStatus · Concert · TimeSlot<br/>conflits, période, publication"]
            d_cat["catalog.py<br/>Artist · Stage · Capacity · EquipmentSet"]
            d_inc["incident.py<br/>Incident · IncidentDescription"]
        end
    end

    subgraph SORTIE["Adaptateurs de sortie — app/infrastructure/"]
        a_repos["sqlalchemy_repositories.py<br/>SqlAlchemyConcertRepository · SqlAlchemyFestivalRepository<br/>SqlAlchemyArtistRepository · SqlAlchemyStageRepository<br/>SqlAlchemyIncidentRepository"]
        a_pending["sqlalchemy_repositories.py<br/>SqlAlchemyPendingNotificationStore"]
        a_mail["email_notifier.py<br/>EmailNotifier"]
    end

    subgraph TECH["Technique"]
        orm["models.py (ORM)<br/>database.py (engine, get_db)"]
        db[("SQLite festiplan.db<br/>tables métier + pending_notifications")]
        mail["utils/email_sender.py<br/>faux envoi d'email<br/>(panne : FESTIPLAN_FAIL_NOTIFICATIONS)"]
    end

    %% Chemin d'une requête HTTP
    client -->|"1. requête HTTP"| routes
    routes --- schemas
    routes --- presenters
    routes --- errors
    routes -->|"2. Depends()"| wiring
    routes -->|"3. execute(command)"| APP

    %% Le cœur
    APP -->|"utilise"| PORTS
    APP -->|"délègue les règles"| DOM

    %% Implémentation des ports : l'adaptateur dépend du port (flèche vers le cœur)
    a_repos -.->|"implémente"| p_repos
    a_pending -.->|"implémente"| p_pending
    a_mail -.->|"implémente"| p_notifier

    %% Composition
    wiring -.->|"instancie"| APP
    wiring -.->|"instancie"| SORTIE

    %% Persistance et notifications
    a_repos -->|"mapping ORM ↔ domaine"| orm
    a_pending --> orm
    orm --> db
    a_mail --> mail

    classDef core fill:#fff3cd,stroke:#b8860b,color:#000
    classDef port fill:#e2f0d9,stroke:#2e7d32,color:#000
    classDef adapter fill:#dbe9f6,stroke:#1f5f9f,color:#000
    classDef tech fill:#eeeeee,stroke:#777,color:#000
    class uc_concert,uc_fest,uc_notif,d_sched,d_cat,d_inc core
    class p_repos,p_pending,p_notifier port
    class routes,schemas,presenters,errors,a_repos,a_pending,a_mail adapter
    class wiring,orm,db,mail tech
```

**Légende :** jaune = cœur (domaine + cas d'utilisation), vert = ports, bleu = adaptateurs, gris = technique.
Flèche pleine = dépendance (« utilise »). Flèche pointillée = « implémente » (de l'adaptateur vers le port qu'il réalise)
ou « instancie » (depuis la racine de composition). Toutes les flèches entre le cœur et les adaptateurs pointent vers le cœur.
Les cinq dépôts sont regroupés dans un seul bloc pour garder le diagramme lisible ; le tableau ci-dessous détaille chaque port.

### Lecture du diagramme

**Où sont le domaine et les cas d'utilisation ?**
Dans `app/domain/` et `app/application/`. Ces modules n'importent ni FastAPI, ni SQLAlchemy, ni la configuration.
Toutes les dépendances vont vers le cœur, jamais dans l'autre sens.

**Ports et adaptateurs qui les implémentent :**

| Port (`app/application/ports.py`) | Adaptateur (`app/infrastructure/`) | Technologie |
|---|---|---|
| `ConcertRepository` | `SqlAlchemyConcertRepository` | SQLAlchemy / SQLite |
| `FestivalRepository` | `SqlAlchemyFestivalRepository` | SQLAlchemy / SQLite |
| `ArtistRepository` | `SqlAlchemyArtistRepository` | SQLAlchemy / SQLite |
| `StageRepository` | `SqlAlchemyStageRepository` | SQLAlchemy / SQLite |
| `IncidentRepository` | `SqlAlchemyIncidentRepository` | SQLAlchemy / SQLite |
| `PendingNotificationStore` | `SqlAlchemyPendingNotificationStore` | table `pending_notifications` |
| `Notifier` | `EmailNotifier` | `utils/email_sender.py` (faux email) |

Dans les tests unitaires (`tests/test_reschedule_use_case.py`, `tests/test_schedule_use_case.py`), ces ports
sont remplacés par des faux en mémoire. C'est ce qui montre que le cœur est vraiment découplé.

**Comment une requête HTTP atteint le cœur :**
1. Le routeur FastAPI reçoit la requête, et Pydantic (`schemas.py`) valide le JSON.
2. `Depends(get_...)` demande à `wiring.py` un cas d'utilisation déjà assemblé avec ses adaptateurs.
3. Le routeur construit une commande (ex. `RescheduleConcertCommand`) et appelle `execute()`.
4. Le résultat est traduit en JSON par `presenters.py`. Les exceptions métier sont traduites en code HTTP par `errors.py`.

**Persistance et notifications :**
`wiring.py` est le seul endroit qui connaît à la fois les cas d'utilisation et les classes concrètes : il instancie les adaptateurs et les injecte dans les cas d'utilisation.
La persistance passe par les dépôts SQLAlchemy, qui convertissent les lignes ORM (`models.py`) en objets du domaine.
Les notifications passent par `EmailNotifier`. En cas d'échec, elles sont stockées dans `pending_notifications`
via `PendingNotificationStore`, puis renvoyées par `RetryPendingNotifications` (`POST /notifications/retry`).

**Écarts assumés :**
- Les routeurs importent `wiring.py`, qui se trouve dans `infrastructure/`. C'est la racine de composition :
  elle doit connaître tout le monde, et ce lien reste limité aux fonctions `get_...` passées à `Depends`.
- `ConcertNotFound` et `FestivalNotFound` sont définies dans leurs modules de cas d'utilisation, puis regroupées dans `application/errors.py`.

## 2. Diagramme de séquence — Déplacer un concert

`PATCH /concerts/{concert_id}/reschedule` avec `{"start_time": ..., "end_time": ...}`.

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant R as Route PATCH reschedule<br/>api/concerts.py
    participant W as wiring.py<br/>get_reschedule_concert
    participant UC as RescheduleConcert<br/>(cas d'utilisation)
    participant CR as SqlAlchemyConcertRepository<br/>«ConcertRepository»
    participant FR as SqlAlchemyFestivalRepository<br/>«FestivalRepository»
    participant C as Concert<br/>(domaine)
    participant F as Festival<br/>(domaine)
    participant N as EmailNotifier<br/>«Notifier»
    participant P as SqlAlchemyPendingNotificationStore<br/>«PendingNotificationStore»
    participant DB as SQLite

    Client->>R: PATCH /concerts/7/reschedule {start_time, end_time}
    Note over R: Pydantic valide le JSON (422 si mal formé)
    R->>W: Depends(get_reschedule_concert)
    W-->>R: RescheduleConcert(repos SQLAlchemy, EmailNotifier, store)
    R->>UC: execute(RescheduleConcertCommand)

    UC->>CR: get(concert_id)
    CR->>DB: SELECT concert
    break Concert introuvable
        CR-->>UC: None
        UC-->>R: raise ConcertNotFound
        R-->>Client: 404 "Concert introuvable"
    end
    CR-->>UC: Concert

    UC->>FR: get(concert.festival_id)
    FR->>DB: SELECT festival
    FR-->>UC: Festival (status preparation / published)

    UC->>UC: TimeSlot(start, end)
    break fin <= début
        UC-->>R: raise InvalidTimeSlot
        R-->>Client: 400 "La date de fin doit être postérieure..."
    end

    UC->>CR: list_for_festival(festival_id)
    CR->>DB: SELECT concerts du festival
    CR-->>UC: autres concerts

    UC->>C: reschedule(new_slot, festival, autres)
    break Concert annulé
        C-->>R: raise ConcertNotReschedulable
        R-->>Client: 409 "Un concert annulé ne peut pas être déplacé"
    end
    C->>F: ensure_schedule_editable()
    break Planning publié
        F-->>R: raise ScheduleLocked
        R-->>Client: 409 "Le planning est publié : dépubliez le festival..."
    end
    C->>C: _check_slot() : créneau dans la période du festival ?
    break Hors période du festival
        C-->>R: raise OutsideFestivalPeriod
        R-->>Client: 400 "Le concert doit se dérouler pendant le festival"
    end
    C->>C: _check_slot() : chevauchement avec un concert non annulé ?
    break Même scène OU même artiste sur un créneau qui chevauche
        C-->>R: raise SchedulingConflict
        R-->>Client: 409 "Conflit : la scène est déjà occupée" / "l'artiste est déjà programmé"
    end
    Note over C,R: Chaque refus ci-dessus remonte via RescheduleConcert jusqu'à la route
    C->>C: slot = new_slot
    C-->>UC: ok

    UC->>CR: save(concert)
    CR->>DB: UPDATE concerts + COMMIT
    Note over UC,DB: ✅ POINT DE VALIDATION : le déplacement est définitivement enregistré.<br/>Plus rien après ne peut l'annuler ni produire une erreur 500.

    UC->>N: notify_or_queue() → send(sujet, message)
    alt Envoi réussi
        N-->>UC: ok
        Note right of UC: NotificationOutcome(SENT)
    else Service indisponible
        N-->>UC: raise NotificationFailed
        UC->>P: add(sujet, message, erreur)
        P->>DB: INSERT pending_notifications + COMMIT
        Note right of UC: NotificationOutcome(PENDING_RETRY)<br/>+ warning dans les logs
    end

    UC-->>R: RescheduleConcertResult(concert, notification)
    R->>R: presenters : concert_out + notification_out
    R-->>Client: 200 {..., "notification": {"status": "sent" | "pending_retry", "detail": ...}}
```

### Points clés

- **Ordre des vérifications :** introuvable → créneau valide → concert annulé → planning publié → période du festival → conflits.
  Au premier refus, l'exception remonte jusqu'à la route en traversant `RescheduleConcert` (qui ne l'intercepte pas),
  puis la route la traduit avec `errors.py`. Pour garder le diagramme lisible, les flèches de refus vont directement à la route.
  Aucune écriture n'a eu lieu, donc la base est inchangée.
- **Où vivent les règles :** les vérifications métier sont dans `Concert.reschedule()` et `Festival.ensure_schedule_editable()`.
  Le cas d'utilisation se contente d'orchestrer : charger, déléguer au domaine, sauvegarder, notifier.
- **Moment de validation :** le `COMMIT` dans `SqlAlchemyConcertRepository.save()`. La notification est envoyée
  après, de façon synchrone. Il n'y a pas de mécanisme asynchrone.
- **Échec de la notification :** il ne transforme pas la réponse en erreur. La réponse est `200` avec
  `"status": "pending_retry"`, et la notification est conservée en base pour être renvoyée.