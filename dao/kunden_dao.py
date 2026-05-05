"""
KundenDAO — Pizzeria Sunshine
=============================
Datenzugriff für die Kunden-Tabelle.

Kapselt alle DB-Operationen, die mit Kunde-Entities zu tun haben.
Wird vom KundenService und AuthService verwendet.

Wichtig: Kein Service und keine Page darf direkt mit der Kunde-Tabelle reden —
immer über diese DAO. So bleibt SQL an einer Stelle und ist später leicht
austauschbar (z. B. wenn wir mal von SQLite auf Postgres wechseln).
"""

from typing import List, Optional

from sqlmodel import select

from domain.models import Kunde
from utils.db import get_session


class KundenDAO:
    """Data Access Object für Kunde-Entities."""

    # ----------------------------------------------------------------------
    # Standard-CRUD
    # ----------------------------------------------------------------------

    @staticmethod
    def create(kunde: Kunde) -> Kunde:
        """Speichert einen neuen Kunden in der DB.

        Das Passwort sollte bereits gehasht sein (passwort_hash gesetzt,
        nicht das Klartext-Passwort) — das macht der AuthService.

        Gibt den Kunden zurück inkl. neu generierter id.
        """
        with get_session() as session:
            session.add(kunde)
            session.commit()
            session.refresh(kunde)  # holt die von SQLite generierte id
            return kunde

    @staticmethod
    def get_by_id(kunden_id: int) -> Optional[Kunde]:
        """Lädt einen Kunden anhand seiner ID. None, wenn nicht gefunden."""
        with get_session() as session:
            return session.get(Kunde, kunden_id)

    @staticmethod
    def update(kunde: Kunde) -> Kunde:
        """Aktualisiert einen bestehenden Kunden.

        Erwartet einen Kunden mit gesetzter id (also einen, der schon in
        der DB existiert). SQLModel erkennt am vorhandenen PK, dass es ein
        UPDATE und kein INSERT ist.
        """
        with get_session() as session:
            session.add(kunde)
            session.commit()
            session.refresh(kunde)
            return kunde

    @staticmethod
    def delete(kunden_id: int) -> bool:
        """Löscht einen Kunden anhand seiner ID.

        Gibt True zurück, wenn gelöscht — False, wenn nicht gefunden.

        Achtung: Der Kunde hat Adressen und Bestellungen. Wenn die noch
        existieren, wirft SQLite einen Foreign-Key-Fehler (PRAGMA ist an).
        Vorher mit AdresseDAO.delete und/oder BestellungDAO aufräumen.
        """
        with get_session() as session:
            kunde = session.get(Kunde, kunden_id)
            if kunde is None:
                return False
            session.delete(kunde)
            session.commit()
            return True

    # ----------------------------------------------------------------------
    # Spezielle Queries
    # ----------------------------------------------------------------------

    @staticmethod
    def finde_per_email(email: str) -> Optional[Kunde]:
        """Findet einen Kunden anhand seiner Email — wird beim Login verwendet.

        Email ist im Modell als unique markiert, gibt also höchstens einen
        Treffer. Suche ist case-sensitive (so wie SQLite es standardmässig macht).
        """
        with get_session() as session:
            statement = select(Kunde).where(Kunde.email == email)
            return session.exec(statement).first()

    @staticmethod
    def email_existiert(email: str) -> bool:
        """Prüft, ob eine Email schon registriert ist.

        Wird bei der Registrierung verwendet, um doppelte Accounts zu
        vermeiden — bevor das unique-Constraint einen Hard-Fail wirft,
        kann der Service eine schöne UI-Meldung zeigen.
        """
        return KundenDAO.finde_per_email(email) is not None

    @staticmethod
    def alle() -> List[Kunde]:
        """Gibt alle Kunden zurück, sortiert nach Nachname, Vorname.

        Für die Admin-Sicht. Im echten Betrieb mit Tausenden Kunden würde
        man Pagination einbauen — fürs Schulprojekt reicht's so.
        """
        with get_session() as session:
            statement = select(Kunde).order_by(Kunde.nachname, Kunde.vorname)
            return list(session.exec(statement).all())