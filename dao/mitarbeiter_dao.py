"""
MitarbeiterDAO — Pizzeria Sunshine
==================================
Datenzugriff für die Mitarbeiter-Tabelle.

Mitarbeiter sind die Personen mit Backoffice-Zugriff (z. B. Bestellungen
übernehmen, Menü pflegen). Login funktioniert analog zum Kunden (Email +
Passwort-Hash), aber separater Pfad — Mitarbeiter sehen die Admin-Seiten,
Kunden sehen das Bestell-Frontend.

Rollen kommen aus dem MitarbeiterRolle-Enum in models.py:
KOCH, FAHRER, ADMIN.
"""

from typing import List, Optional

from sqlmodel import select

from domain.models import Mitarbeiter, MitarbeiterRolle
from utils.db import get_session


class MitarbeiterDAO:
    """Data Access Object für Mitarbeiter-Entities."""

    # ----------------------------------------------------------------------
    # Standard-CRUD
    # ----------------------------------------------------------------------

    @staticmethod
    def create(mitarbeiter: Mitarbeiter) -> Mitarbeiter:
        """Speichert einen neuen Mitarbeiter.

        Das Passwort sollte bereits gehasht sein — analog zum Kunden.
        Das Anlegen passiert im Admin-Bereich oder per Initial-Seeding.
        """
        with get_session() as session:
            session.add(mitarbeiter)
            session.commit()
            session.refresh(mitarbeiter)
            return mitarbeiter

    @staticmethod
    def get_by_id(mitarbeiter_id: int) -> Optional[Mitarbeiter]:
        with get_session() as session:
            return session.get(Mitarbeiter, mitarbeiter_id)

    @staticmethod
    def update(mitarbeiter: Mitarbeiter) -> Mitarbeiter:
        with get_session() as session:
            session.add(mitarbeiter)
            session.commit()
            session.refresh(mitarbeiter)
            return mitarbeiter

    @staticmethod
    def delete(mitarbeiter_id: int) -> bool:
        """Löscht einen Mitarbeiter.

        In der Praxis besser: aktiv=False setzen (siehe deaktivieren()),
        weil Bestellungen auf den Mitarbeiter verweisen können. Hard-Delete
        nur, wenn der Mitarbeiter noch keine Bestellungen bearbeitet hat.
        """
        with get_session() as session:
            mitarbeiter = session.get(Mitarbeiter, mitarbeiter_id)
            if mitarbeiter is None:
                return False
            session.delete(mitarbeiter)
            session.commit()
            return True

    # ----------------------------------------------------------------------
    # Spezielle Queries
    # ----------------------------------------------------------------------

    @staticmethod
    def finde_per_email(email: str) -> Optional[Mitarbeiter]:
        """Findet einen Mitarbeiter anhand seiner Email — für den Login."""
        with get_session() as session:
            statement = select(Mitarbeiter).where(Mitarbeiter.email == email)
            return session.exec(statement).first()

    @staticmethod
    def email_existiert(email: str) -> bool:
        """Prüft, ob die Email bereits einem Mitarbeiter zugeordnet ist."""
        return MitarbeiterDAO.finde_per_email(email) is not None

    @staticmethod
    def alle() -> List[Mitarbeiter]:
        """Gibt alle Mitarbeiter zurück, sortiert nach Nachname.

        Wird auf der Admin-Seite verwendet.
        """
        with get_session() as session:
            statement = select(Mitarbeiter).order_by(
                Mitarbeiter.nachname, Mitarbeiter.vorname
            )
            return list(session.exec(statement).all())

    @staticmethod
    def alle_aktiven() -> List[Mitarbeiter]:
        """Nur Mitarbeiter mit aktiv=True. Für Listen, in denen man
        Bestellungen zuweisen kann — deaktivierte Mitarbeiter sollen da
        nicht mehr auftauchen.
        """
        with get_session() as session:
            statement = (
                select(Mitarbeiter)
                .where(Mitarbeiter.aktiv == True)  # noqa: E712
                .order_by(Mitarbeiter.nachname, Mitarbeiter.vorname)
            )
            return list(session.exec(statement).all())

    @staticmethod
    def alle_mit_rolle(rolle: MitarbeiterRolle) -> List[Mitarbeiter]:
        """Filtert Mitarbeiter nach Rolle (z. B. nur ADMIN, nur FAHRER).

        Praktisch im Admin-UI für die Übersicht "Wer ist Fahrer?".
        """
        with get_session() as session:
            statement = (
                select(Mitarbeiter)
                .where(Mitarbeiter.rolle == rolle)
                .order_by(Mitarbeiter.nachname, Mitarbeiter.vorname)
            )
            return list(session.exec(statement).all())

    @staticmethod
    def deaktivieren(mitarbeiter_id: int) -> bool:
        """Setzt aktiv=False statt zu löschen.

        Soft-Delete: Mitarbeiter bleibt für historische Bestellungen
        nachvollziehbar, taucht aber nicht mehr in aktiven Listen auf.
        """
        with get_session() as session:
            mitarbeiter = session.get(Mitarbeiter, mitarbeiter_id)
            if mitarbeiter is None:
                return False
            mitarbeiter.aktiv = False
            session.add(mitarbeiter)
            session.commit()
            return True