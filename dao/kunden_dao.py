"""
DAO — Kunde
============
Datenbank-Zugriff für die Tabelle `kunde`.

Ein Kunde ist die Person, die im Frontend bestellt. Er hat einen Login
(Email + Passwort-Hash), eine oder mehrere Adressen (siehe `AdresseDAO`)
und eine Bestellhistorie (siehe `BestellungDAO` vom Bestell-Team).

Diese DAO kapselt alle SQL-/ORM-Aufrufe rund um die Kunde-Tabelle und
wird vom `KundenService` und vom `AuthService` verwendet. Pages oder
andere Services dürfen NICHT direkt mit der Tabelle reden — immer über
die DAO. So bleibt SQL an einer Stelle und ist später leicht austauschbar.

Designentscheidungen:
  - Statische Methoden, weil die DAO keinen Zustand hat. Die Session
    wird von aussen reingegeben (vom Service oder Test). Vorteil: Mehrere
    DAO-Aufrufe können dieselbe Session teilen und damit in einer
    Transaktion laufen — z. B. „Kunde anlegen + erste Adresse anlegen"
    soll entweder ganz klappen oder gar nicht.
  - Rückgabewerte sind immer Domain-Objekte (`Kunde`), nie Tupel oder
    Dicts. Dadurch bleibt die Service-Schicht frei von ORM-Details.
  - Kein `commit()` in der DAO. Wer die Transaktion startet (der Service
    via `get_session()`), schliesst sie auch ab. So bleibt das Verhalten
    vorhersagbar und Tests sind einfacher.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Kunde


class KundenDAO:
    """Persistenz-Operationen für `Kunde`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, kunde: Kunde) -> Kunde:
        """Speichert einen neuen Kunden und gibt ihn inkl. ID zurück.

        `flush()` + `refresh()` befüllen die generierte Primary-Key-ID
        sofort. Der Service braucht sie z. B., um direkt danach eine
        erste Adresse via `AdresseDAO` zu verknüpfen.

        Das Passwort muss bereits gehasht sein (`passwort_hash` gesetzt,
        nicht das Klartext-Passwort) — das macht der `AuthService`.
        Wer hier ein Klartext-Passwort reinschiebt, hat einen Bug.
        """
        session.add(kunde)
        session.flush()
        session.refresh(kunde)
        return kunde

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, kunden_id: int) -> Optional[Kunde]:
        """Lädt einen Kunden über seine Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert. Die Service-
        Schicht entscheidet, ob daraus eine Exception oder eine UI-
        Meldung wird.
        """
        return session.get(Kunde, kunden_id)

    @staticmethod
    def finde_per_email(session: Session, email: str) -> Optional[Kunde]:
        """Findet einen Kunden anhand seiner Email — Hauptanwendung: Login.

        Email ist im Modell als `unique` markiert, gibt also höchstens
        einen Treffer. Suche ist case-sensitive (SQLite-Default) — der
        `AuthService` sollte die Eingabe vorher normalisieren (lowercase
        + strip), damit „Max@Beispiel.ch" und „max@beispiel.ch" als
        derselbe Account erkannt werden.
        """
        statement = select(Kunde).where(Kunde.email == email)
        return session.exec(statement).first()

    @staticmethod
    def email_existiert(session: Session, email: str) -> bool:
        """Prüft, ob eine Email schon registriert ist.

        Günstige Vorab-Prüfung bei der Registrierung — bevor das UNIQUE-
        Constraint einen Hard-Fail wirft, kann der Service eine schöne
        UI-Meldung zeigen („Diese Email wird bereits verwendet").
        """
        return KundenDAO.finde_per_email(session, email) is not None

    @staticmethod
    def alle(session: Session, *, sortiert: bool = True) -> list[Kunde]:
        """Liefert alle Kunden.

        Bei `sortiert=True` (Default) zuerst nach Nachname, dann Vorname —
        die übliche Admin-Sicht. Wer die Reihenfolge selbst bestimmen
        will (z. B. Tests), setzt `sortiert=False`.

        Im echten Betrieb mit Tausenden Kunden würde man Pagination
        einbauen — fürs Schulprojekt mit ~50 Test-Kunden reicht das so.
        """
        statement = select(Kunde)
        if sortiert:
            statement = statement.order_by(Kunde.nachname, Kunde.vorname)
        return list(session.exec(statement).all())

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, kunde: Kunde) -> Kunde:
        """Schreibt Änderungen eines bereits geladenen Kunden zurück.

        Erwartet, dass `kunde.id` gesetzt ist (also das Objekt aus einem
        vorherigen `get_*` stammt). SQLAlchemy erkennt anhand der ID,
        dass es ein UPDATE und kein INSERT braucht.

        Typische Updates: Telefonnummer ändern, Namen korrigieren.
        Email-Änderung ist heikel (Konflikt mit UNIQUE) — das prüft der
        Service vorher mit `email_existiert()`.
        """
        session.add(kunde)
        session.flush()
        session.refresh(kunde)
        return kunde

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, kunden_id: int) -> bool:
        """Löscht einen Kunden über seine ID.

        Rückgabe:
          - True, falls ein Kunde gelöscht wurde
          - False, falls die ID nicht existierte

        Achtung: Der Kunde hat Adressen und Bestellungen. Wenn die noch
        existieren, schlägt das wegen Foreign-Key-Constraint fehl (PRAGMA
        ist an). Vorher mit `AdresseDAO.delete` und/oder über das Bestell-
        Team aufräumen — oder den Kunden stattdessen als „inaktiv"
        markieren (wäre eine Modell-Erweiterung).
        """
        kunde = session.get(Kunde, kunden_id)
        if kunde is None:
            return False
        session.delete(kunde)
        session.flush()
        return True