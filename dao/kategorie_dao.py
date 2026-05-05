"""
DAO — Kategorie
================
Datenbank-Zugriff für die Tabelle `kategorie`.

Eine Kategorie ist die oberste Gliederung im Menü (Pizza, Pasta, Getränke …)
und hat eine 1:N-Beziehung zu Artikeln. Diese DAO kapselt alle SQL-/ORM-
Aufrufe rund um die Kategorie-Tabelle.

Designentscheidungen:
  - Statische Methoden, weil die DAO keinen Zustand hat. Die Session
    wird von aussen reingegeben (vom Service oder Test). Vorteil: Mehrere
    DAO-Aufrufe können dieselbe Session teilen und damit in einer
    Transaktion laufen.
  - Rückgabewerte sind immer Domain-Objekte (`Kategorie`), nie Tupel
    oder Dicts. Dadurch bleibt die Service-Schicht frei von ORM-Details.
  - Kein `commit()` in der DAO. Wer die Transaktion startet, schliesst
    sie auch ab. So bleibt das Verhalten vorhersagbar (siehe
    `utils/db.py` — `get_session()` committet am Ende des with-Blocks).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Kategorie


class KategorieDAO:
    """Persistenz-Operationen für `Kategorie`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, kategorie: Kategorie) -> Kategorie:
        """Speichert eine neue Kategorie und gibt sie inkl. ID zurück.

        `flush()` zwingt SQLAlchemy, das INSERT sofort auszuführen und
        damit die generierte Primary-Key-ID auf das Objekt zu schreiben.
        Ohne flush würde die ID erst beim Commit gesetzt — ein Service,
        der die ID direkt weiterverwenden will (z. B. für eine
        Foreign-Key-Beziehung), bekäme sonst `None`.
        """
        session.add(kategorie)
        session.flush()
        session.refresh(kategorie)
        return kategorie

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, kategorie_id: int) -> Optional[Kategorie]:
        """Lädt eine Kategorie über ihre Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert. Die Service-
        Schicht entscheidet, ob daraus eine Exception oder eine UI-
        Meldung wird.
        """
        return session.get(Kategorie, kategorie_id)

    @staticmethod
    def get_by_name(session: Session, name: str) -> Optional[Kategorie]:
        """Lädt eine Kategorie über ihren Namen.

        Der Name ist im Modell als `unique` markiert — es gibt also
        höchstens einen Treffer. Diese Methode wird vor allem im Admin-
        Bereich benutzt, um Duplikate beim Anlegen zu vermeiden.
        """
        statement = select(Kategorie).where(Kategorie.name == name)
        return session.exec(statement).first()

    @staticmethod
    def get_all(session: Session, *, sortiert: bool = True) -> list[Kategorie]:
        """Liefert alle Kategorien.

        Bei `sortiert=True` (Default) wird zuerst nach dem Feld
        `sortierung` und dann alphabetisch nach `name` geordnet — genau
        so, wie das Menü im Browser angezeigt werden soll. Wer die
        Reihenfolge selbst bestimmen will (z. B. Tests), setzt
        `sortiert=False`.
        """
        statement = select(Kategorie)
        if sortiert:
            statement = statement.order_by(Kategorie.sortierung, Kategorie.name)
        return list(session.exec(statement).all())

    @staticmethod
    def exists(session: Session, name: str) -> bool:
        """Prüft, ob eine Kategorie mit diesem Namen bereits existiert.

        Gedacht als günstige Vorab-Prüfung im Service, bevor ein
        `create()` evtl. mit einem UNIQUE-Constraint-Fehler scheitert.
        Spart der UI eine ausgelöste Exception.
        """
        return KategorieDAO.get_by_name(session, name) is not None

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, kategorie: Kategorie) -> Kategorie:
        """Schreibt Änderungen einer bereits geladenen Kategorie zurück.

        Erwartet, dass `kategorie.id` gesetzt ist (also das Objekt aus
        einem vorherigen `get_*` stammt oder eine bekannte ID hat).
        SQLAlchemy erkennt anhand der ID, dass es ein UPDATE und kein
        INSERT braucht.
        """
        session.add(kategorie)  # session.add() funktioniert auch als merge bei vorhandener ID
        session.flush()
        session.refresh(kategorie)
        return kategorie

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, kategorie_id: int) -> bool:
        """Löscht eine Kategorie über ihre ID.

        Rückgabe:
          - True, falls eine Kategorie gelöscht wurde
          - False, falls die ID nicht existierte

        Achtung: Eine Kategorie mit zugeordneten Artikeln kann nicht
        gelöscht werden — der FK-Constraint (siehe
        `_foreign_keys_aktivieren` in `utils/db.py`) verhindert das mit
        einer IntegrityError. Das ist gewollt: Der Service soll erst die
        Artikel umhängen oder die Kategorie als „nicht aktiv" markieren.
        """
        kategorie = session.get(Kategorie, kategorie_id)
        if kategorie is None:
            return False
        session.delete(kategorie)
        session.flush()
        return True
