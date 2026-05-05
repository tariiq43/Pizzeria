"""
DAO — ArtikelZutat (Junction)
==============================
Datenbank-Zugriff für die Tabelle `artikel_zutat`.

Diese Junction-Tabelle bildet das Standard-Rezept eines Artikels ab:
welche Zutaten gehören in welcher Menge in eine Pizza Margherita?
Sie ist NICHT für Wunschpizza-Zutaten zuständig — das macht die separate
Tabelle `wunsch_zutat` (Bestell-Team).

Besonderheiten dieser Tabelle:
  - Composite Primary Key aus (`artikel_id`, `zutat_id`). Ein Artikel
    kann eine bestimmte Zutat also nur einmal als Standard-Zutat haben
    (zweimal Mozzarella im Rezept ergibt keinen Sinn — wer mehr will,
    erhöht stattdessen die `menge`).
  - Eigenes Attribut `menge` auf der Junction. Deshalb kein einfacher
    Many-to-Many ohne Daten, sondern eine richtige Tabelle mit DAO.

Designentscheidungen:
  - `zutat_hinzufuegen` ist strikt: schlägt fehl, wenn die Kombination
    schon existiert. So merken wir Bugs früh. Wer aktualisieren will,
    nimmt explizit `menge_aktualisieren`.
  - `rezept_laden` lädt die Junction-Einträge eager mit ihrer `Zutat`-
    Relation (selectinload). Damit kann die UI über
    `eintrag.zutat.name` zugreifen, ohne dass die Session noch offen
    sein muss — wichtig, weil NiceGUI-Render und DB-Session zeitlich
    auseinanderdriften können.
  - Kein `commit()` in der DAO (gleicher Vertrag wie die anderen DAOs).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import selectinload
from sqlmodel import Session, delete, select

from domain.models import ArtikelZutat


class ArtikelZutatDAO:
    """Persistenz-Operationen für `ArtikelZutat` (Standard-Rezept)."""

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get(
        session: Session, artikel_id: int, zutat_id: int
    ) -> Optional[ArtikelZutat]:
        """Lädt einen einzelnen Junction-Eintrag.

        Composite Primary Key: SQLModel/SQLAlchemy erwartet als Key ein
        Tupel in der Reihenfolge der Felder im Modell.
        """
        return session.get(ArtikelZutat, (artikel_id, zutat_id))

    @staticmethod
    def existiert(session: Session, artikel_id: int, zutat_id: int) -> bool:
        """Prüft, ob die Kombination (artikel_id, zutat_id) im Rezept ist.

        Günstige Vorab-Prüfung im Service — spart eine IntegrityError,
        wenn man eine Zutat ein zweites Mal hinzufügen wollte.
        """
        return ArtikelZutatDAO.get(session, artikel_id, zutat_id) is not None

    @staticmethod
    def rezept_laden(session: Session, artikel_id: int) -> list[ArtikelZutat]:
        """Liefert alle Junction-Einträge eines Artikels (= das Standard-Rezept).

        Eager-loading der `Zutat`-Relation: Der Aufrufer kann später
        `eintrag.zutat.name` lesen, ohne dass eine zusätzliche Query
        ausgelöst wird oder die Session noch offen sein muss. Das ist
        gerade in NiceGUI-Pages wichtig, wo das Render asynchron passiert
        und die DB-Session schon längst geschlossen sein kann.

        Sortierung nach Zutat-ID, damit zwei Aufrufe dieselbe Reihenfolge
        liefern — wichtig für UI-Stabilität und Tests.
        """
        statement = (
            select(ArtikelZutat)
            .where(ArtikelZutat.artikel_id == artikel_id)
            .options(selectinload(ArtikelZutat.zutat))
            .order_by(ArtikelZutat.zutat_id)
        )
        return list(session.exec(statement).all())

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def zutat_hinzufuegen(
        session: Session,
        artikel_id: int,
        zutat_id: int,
        menge: Decimal = Decimal("1"),
    ) -> ArtikelZutat:
        """Fügt einer Pizza eine Standard-Zutat hinzu.

        Strikt: Wenn die Kombination bereits existiert, lässt der DB-
        Constraint (Composite PK) den INSERT scheitern und SQLAlchemy
        wirft eine IntegrityError. Das ist gewollt — zweimal die gleiche
        Zutat im Rezept ist fachlich Quatsch, und ein stiller Upsert
        würde Bugs verstecken.

        Wer eine bestehende Zutat anders dosieren will, ruft
        `menge_aktualisieren()` auf. Wer „Add or update" will,
        kombiniert beides im Service.
        """
        eintrag = ArtikelZutat(
            artikel_id=artikel_id, zutat_id=zutat_id, menge=menge
        )
        session.add(eintrag)
        session.flush()
        session.refresh(eintrag)
        return eintrag

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def menge_aktualisieren(
        session: Session, artikel_id: int, zutat_id: int, menge: Decimal
    ) -> Optional[ArtikelZutat]:
        """Setzt die Menge einer Zutat im Standard-Rezept neu.

        Convenience für den Admin: „Pizza Margherita braucht jetzt 1.5
        statt 1 Mozzarella". Spart Laden → Mutieren → Speichern.
        Gibt das aktualisierte Objekt zurück oder `None`, falls die
        Kombination nicht existiert (dann sollte der Service stattdessen
        `zutat_hinzufuegen` aufrufen).
        """
        eintrag = ArtikelZutatDAO.get(session, artikel_id, zutat_id)
        if eintrag is None:
            return None
        eintrag.menge = menge
        session.add(eintrag)
        session.flush()
        session.refresh(eintrag)
        return eintrag

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def zutat_entfernen(
        session: Session, artikel_id: int, zutat_id: int
    ) -> bool:
        """Entfernt eine Zutat aus dem Standard-Rezept eines Artikels.

        Rückgabe:
          - True, falls ein Eintrag entfernt wurde
          - False, falls die Kombination nicht existierte (idempotent
            sicher: doppelter Aufruf ist kein Fehler, sondern liefert
            False).

        Hinweis: Das wirkt sich nur auf zukünftige Bestellungen aus.
        Bestehende Bestellungen sind davon unberührt — sie speichern
        ihre Wunsch-Zutaten in `wunsch_zutat`, nicht hier.
        """
        eintrag = ArtikelZutatDAO.get(session, artikel_id, zutat_id)
        if eintrag is None:
            return False
        session.delete(eintrag)
        session.flush()
        return True

    @staticmethod
    def rezept_loeschen(session: Session, artikel_id: int) -> int:
        """Entfernt alle Standard-Zutaten eines Artikels.

        Rückgabe: Anzahl der entfernten Einträge.

        Hauptverwendung: Im Service, wenn ein Rezept komplett ersetzt
        werden soll. Der Service ruft erst `rezept_loeschen()` und dann
        mehrmals `zutat_hinzufuegen()` — alles innerhalb derselben
        Session, also einer Transaktion. Wenn beim Hinzufügen etwas
        scheitert, wird durch den Rollback in `get_session()` das alte
        Rezept wiederhergestellt.

        Wir verwenden ein bulk-DELETE statt einzelne `session.delete()`-
        Aufrufe — eine SQL-Anweisung statt N. Bei einer Pizza mit 3-5
        Zutaten kein riesiger Unterschied, aber sauberer Stil.
        """
        statement = delete(ArtikelZutat).where(
            ArtikelZutat.artikel_id == artikel_id
        )
        result = session.exec(statement)
        session.flush()
        # `rowcount` gibt die Anzahl betroffener Zeilen zurück.
        # Bei SQLite immer zuverlässig; bei anderen Backends könnte -1
        # zurückkommen, das interpretieren wir dann als „unbekannt -> 0".
        return result.rowcount if result.rowcount and result.rowcount > 0 else 0
