"""Erreurs applicatives : un objet demandé n'existe pas (R4, R10).

Ce ne sont pas des règles métier : il faut interroger un repository pour les
détecter, c'est donc le cas d'utilisation qui les lève.
"""
from app.application.festival_publication import FestivalNotFound
from app.application.reschedule_concert import ConcertNotFound


class ArtistNotFound(Exception):
    pass


class StageNotFound(Exception):
    pass


__all__ = ["ArtistNotFound", "ConcertNotFound", "FestivalNotFound", "StageNotFound"]
