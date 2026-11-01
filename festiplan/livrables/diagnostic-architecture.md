# Diagnostic de l’architecture initiale

## 1. Vue d’ensemble

FestiPlan est une API FastAPI. Les routes appellent souvent des services, qui utilisent des repositories pour accéder à la base. Mais cette séparation n’est pas toujours respectée : certains services et certaines routes font eux-mêmes des requêtes SQLAlchemy.

```text
Client HTTP
    |
    v
Routes FastAPI ------> SQLAlchemy ------> Base de données
    |
    v
Services ------------> SQLAlchemy
    |
    v
Repositories --------> SQLAlchemy

Services ---> Notifications ---> Faux envoi d’e-mail
```

En résumé, les routes ne passent pas toutes par les services et les services ne passent pas tous par les repositories.

## 2. Responsabilités des principales parties

- **Routes (`app/api/`)** : reçoivent les requêtes et renvoient les réponses HTTP. Elles appellent souvent un service, mais certaines accèdent directement à la base ou vérifient des règles métier.
- **Services (`app/services/`)** : gèrent les principales opérations, comme la création ou le déplacement d’un concert. Ils appliquent une partie des règles métier, mais utilisent aussi directement SQLAlchemy.
- **Repositories (`app/repositories/`)** : regroupent des opérations courantes sur la base, comme retrouver ou créer un concert. Les routes et les services peuvent toutefois les contourner.
- **Modèles (`app/models.py`)** : représentent les tables et leurs relations SQLAlchemy : `Festival`, `Artist`, `Stage`, `Concert` et `Incident`. Il n’y a pas de modèle métier séparé des modèles de base de données.
- **Schémas (`app/schemas.py`)** : décrivent les données reçues et renvoyées par l’API avec Pydantic. Ils vérifient entre autres le format des données et certaines contraintes, comme la capacité positive d’une scène.
- **Base et configuration (`app/database.py`, `app/config.py`)** : configurent la connexion à la base, les sessions SQLAlchemy et les paramètres de l’application.
- **Notifications (`app/services/notification_service.py`, `app/utils/email_sender.py`)** : simulent l’envoi d’un e-mail. Le service de notification appelle directement la fonction d’envoi.

## 3. Dépendances et emplacement des règles métier

Les routes utilisent FastAPI (`APIRouter`, `Depends`, `HTTPException`) et reçoivent une session SQLAlchemy via `get_db`. Les services et les repositories utilisent eux aussi SQLAlchemy. Par exemple, `SchedulingService` interroge les modèles `Concert`, `Festival`, `Artist` et `Stage`, puis enregistre les changements avec `commit()`.

Les schémas Pydantic vérifient certaines données à l’entrée, mais les règles métier se trouvent à plusieurs endroits :

- La création d’un concert vérifie dans `SchedulingService` que les références existent, que la scène appartient au festival, que les dates sont cohérentes, que le concert reste dans les dates du festival, qu’il n’y a pas de conflit de scène ou d’artiste et que les équipements requis sont disponibles.
- La fin d’un concert doit être postérieure à son début : ce contrôle apparaît à la fois dans la route de déplacement et dans `SchedulingService`.
- La capacité strictement positive d’une scène et la description minimale d’un incident sont vérifiées par les schémas Pydantic.
- La route des incidents vérifie elle-même que le concert existe et crée directement l’incident en base.
- La publication change le statut du festival dans `PublicationService`, mais ne vérifie pas les conflits de programmation avant de publier.

Résultat : une règle peut être appliquée à la création d’un concert, mais oubliée lorsqu’on le déplace.

## 4. Exemple concret de responsabilité mal placée

Dans `app/api/concerts.py`, la route `reschedule_concert` cherche elle-même le concert avec `db.query(Concert)` et vérifie l’ordre des dates avant d’appeler le service. Ensuite, `SchedulingService.reschedule_concert` modifie le modèle SQLAlchemy, fait le `commit()` et envoie une notification.

La responsabilité est donc répartie entre la route et le service. La route fait plus que gérer HTTP : elle cherche le concert et vérifie une règle métier. De plus, le service ne refait pas tous les contrôles de la création : il ne vérifie ni les conflits de planning, ni les dates du festival, ni son statut de publication. Un concert peut donc être déplacé dans une situation qui devrait être interdite.

On retrouve le même problème dans `app/api/incidents.py` : la route vérifie que le concert existe, crée l’objet `Incident` et l’enregistre directement en base, sans service ni repository.

## 5. Dépendances directes à FastAPI et SQLAlchemy

- **FastAPI** sert surtout à définir les routes et les réponses HTTP dans `app/api/`. `app/main.py` assemble l’application et ses routeurs.
- **SQLAlchemy** configure la base dans `app/database.py` et définit les modèles dans `app/models.py`. Il est utilisé dans les repositories, mais aussi directement dans certains services et certaines routes.
- Les services n’importent pas FastAPI, ce qui évite de les lier directement au framework web. Par contre, ils dépendent de SQLAlchemy et reçoivent parfois des schémas Pydantic, comme `ConcertCreate` ou `ConcertReschedule`. Ils restent donc liés à la base et aux données de l’API.
- Pour les notifications, `NotificationService` appelle directement `send_email` au lieu de passer par un contrat indépendant de l’outil d’envoi.

## 6. Testabilité et risques d’incohérence

Les tests utilisent `TestClient` et une base SQLite temporaire. Ils vérifient quelques validations et réponses HTTP, par exemple une capacité invalide, des dates de festival incorrectes ou une publication pour un festival inexistant. C’est un bon début pour tester l’API.

Mais les règles métier importantes sont encore peu testées. Malgré son nom, `tests/test_scheduling.py` vérifie seulement que le endpoint de santé répond. Aucun test ne vérifie les conflits de concerts, l’échec d’une notification après l’enregistrement d’un déplacement ou le déplacement d’un concert après publication. Il n’y a pas non plus de tests du domaine indépendants de FastAPI et de SQLite, car le domaine n’est pas séparé dans une couche dédiée.

Les principaux risques sont donc :

- une règle peut être oubliée dans une opération, comme les contrôles de programmation lors d’un déplacement ;
- une notification peut échouer après le `commit()` : le déplacement est enregistré, mais l’API peut quand même répondre avec une erreur HTTP 500 ;
- un concert peut être déplacé alors que son festival est publié ;
- les services sont difficiles à tester seuls, car ils ont besoin d’une session SQLAlchemy et utilisent les modèles de la base ;
- changer la façon d’accéder à la base pourrait obliger à modifier plusieurs couches.

## Conclusion

Les dossiers routes, services et repositories sont déjà là, mais leurs rôles se chevauchent. Les règles métier sont dispersées, les services dépendent de SQLAlchemy et certaines routes accèdent directement à la base. Pour la suite de la refactorisation, l’objectif sera de mieux isoler les règles métier et de laisser les routes gérer HTTP, tandis que les repositories s’occuperont de la persistance.
