"""
DAO — Mitarbeiter
==================
Datenbank-Zugriff für die Tabelle `mitarbeiter`.

Mitarbeiter sind die Personen mit Backoffice-Zugriff (Bestellungen
übernehmen, Menü pflegen, Auslieferungen koordinieren). Login funktioniert
analog zum Kunden (Email + Passwort-Hash), aber separater Pfad —
Mitarbeiter sehen die Admin-Seiten, Kunden das Bestell-Frontend.

Rollen kommen aus dem `MitarbeiterRolle`-Enum in `domain/models.py`:
KOCH, FAHRER, ADMIN.

Designentscheidungen:
  - `delete()` existiert, sollte im Produktivbetrieb aber selten genutzt
    werden — alte Bestellungen verweisen auf den Mitarbeiter (Wer hat
    die Pizza gebacken? Wer hat ausgeliefert?). Stattdessen `deaktivieren()`
    aufrufen — das ist ein Soft-Delete via `aktiv=False`.
  - `alle_aktiven()` und `alle_mit_rolle()` sind eigene Methoden, weil
    sie die häufigsten Filter im Admin-UI sind. So bleibt der Service-
    Code lesbar.
  - Kein `commit()` in der DAO (gleicher Vertrag wie die anderen DAOs).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Mitarbeiter, MitarbeiterRolle


class MitarbeiterDAO:
    """Persistenz-Operationen für `Mitarbeiter`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, mitarbeiter: Mitarbeiter) -> Mitarbeiter:
        """Speichert einen neuen Mitarbeiter und gibt ihn inkl. ID zurück.

        Das Passwort muss bereits gehasht sein — analog zum Kunden. Das
        Anlegen passiert im Admin-Bereich oder per Initial-Seeding beim
        ersten Start (siehe `utils.db.initialisiere_db`).
        """
        session.add(mitarbeiter)
        session.flush()
        session.refresh(mitarbeiter)
        return mitarbeiter

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(
        session: Session, mitarbeiter_id: int
    ) -> Optional[Mitarbeiter]:
        """Lädt einen Mitarbeiter über seine Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert.
        """
        return session.get(Mitarbeiter, mitarbeiter_id)

    @staticmethod
    def finde_per_email(session: Session, email: str) -> Optional[Mitarbeiter]:
        """Findet einen Mitarbeiter anhand seiner Email — für den Login.

        Email ist im Modell `unique`, gibt höchstens einen Treffer.
        Der `AuthService` normalisiert die Eingabe vorher (lowercase +
        strip), damit Tippfehler in Gross-/Kleinschreibung kein Problem
        sind.
        """
        statement = select(Mitarbeiter).where(Mitarbeiter.email == email)
        return session.exec(statement).first()

    @staticmethod
    def email_existiert(session: Session, email: str) -> bool:
        """Prüft, ob die Email bereits einem Mitarbeiter zugeordnet ist.

        Günstige Vorab-Prüfung im Admin, bevor `create()` evtl. mit
        einem UNIQUE-Constraint-Fehler scheitert.
        """
        return MitarbeiterDAO.finde_per_email(session, email) is not None

    @staticmethod
    def alle(session: Session, *, sortiert: bool = True) -> list[Mitarbeiter]:
        """Liefert alle Mitarbeiter (auch deaktivierte).

        Bei `sortiert=True` (Default) nach Nachname, dann Vorname — die
        übliche Admin-Sicht. Wer auch deaktivierte Mitarbeiter ausblenden
        will, nimmt `alle_aktiven()`.
        """
        statement = select(Mitarbeiter)
        if sortiert:
            statement = statement.order_by(
                Mitarbeiter.nachname, Mitarbeiter.vorname
            )
        return list(session.exec(statement).all())

    @staticmethod
    def alle_aktiven(session: Session) -> list[Mitarbeiter]:
        """Nur Mitarbeiter mit `aktiv=True`.

        Für Listen, in denen man Bestellungen zuweisen kann — deaktivierte
        Mitarbeiter sollen dort nicht mehr auftauchen. Sortierung: nach
        Nachname, Vorname.
        """
        statement = (
            select(Mitarbeiter)
            .where(Mitarbeiter.aktiv.is_(True))
            .order_by(Mitarbeiter.nachname, Mitarbeiter.vorname)
        )
        return list(session.exec(statement).all())

    @staticmethod
    def alle_mit_rolle(
        session: Session,
        rolle: MitarbeiterRolle,
        *,
        nur_aktive: bool = False,
    ) -> list[Mitarbeiter]:
        """Filtert Mitarbeiter nach Rolle (z. B. nur ADMIN, nur FAHRER).

        Praktisch im Admin-UI für die Übersicht „Wer ist Fahrer?". Mit
        `nur_aktive=True` werden deaktivierte ausgeblendet — sinnvoll z. B.
        beim Zuweisen einer Auslieferung.
        """
        statement = select(Mitarbeiter).where(Mitarbeiter.rolle == rolle)
        if nur_aktive:
            statement = statement.where(Mitarbeiter.aktiv.is_(True))
        statement = statement.order_by(
            Mitarbeiter.nachname, Mitarbeiter.vorname
        )
        return list(session.exec(statement).all())

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, mitarbeiter: Mitarbeiter) -> Mitarbeiter:
        """Schreibt Änderungen eines bereits geladenen Mitarbeiters zurück.

        Erwartet, dass `mitarbeiter.id` gesetzt ist. SQLAlchemy erkennt
        das und macht ein UPDATE statt INSERT.

        Typische Updates: Rolle ändern, Namen korrigieren. Das Passwort
        ändert man besser über den `AuthService` (der das Hashing macht).
        """
        session.add(mitarbeiter)
        session.flush()
        session.refresh(mitarbeiter)
        return mitarbeiter

    @staticmethod
    def deaktivieren(session: Session, mitarbeiter_id: int) -> bool:
        """Setzt `aktiv=False` statt zu löschen.

        Soft-Delete: Mitarbeiter bleibt für historische Bestellungen
        nachvollziehbar, taucht aber nicht mehr in aktiven Listen auf.
        Diese Methode ist im Produktivbetrieb der bevorzugte Weg, einen
        Mitarbeiter „loszuwerden" — siehe Modul-Docstring.

        Rückgabe:
          - True, falls erfolgreich deaktiviert
          - False, falls die ID nicht existiert
        """
        mitarbeiter = session.get(Mitarbeiter, mitarbeiter_id)
        if mitarbeiter is None:
            return False
        mitarbeiter.aktiv = False
        session.add(mitarbeiter)
        session.flush()
        return True

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, mitarbeiter_id: int) -> bool:
        """Löscht einen Mitarbeiter über seine ID (Hard-Delete).

        Rückgabe:
          - True, falls ein Mitarbeiter gelöscht wurde
          - False, falls die ID nicht existierte

        Achtung: Bestellungen können auf den Mitarbeiter verweisen
        (`mitarbeiter_id` als FK). Wenn welche existieren, schlägt das
        wegen Foreign-Key-Constraint fehl. Im Normalfall stattdessen
        `deaktivieren()` aufrufen — siehe Modul-Docstring.
        """
        mitarbeiter = session.get(Mitarbeiter, mitarbeiter_id)
        if mitarbeiter is None:
            return False
        session.delete(mitarbeiter)
        session.flush()
        return True