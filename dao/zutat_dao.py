"""
DAO — Zutat
============
Datenbank-Zugriff für die Tabelle `zutat`.

Eine Zutat (Käse, Salami, Pilze …) wird an zwei Stellen verwendet:
  1. Als Standard-Zutat eines Artikels (über `artikel_zutat`)
  2. Als frei wählbare Zutat einer Wunschpizza (über `wunsch_zutat`)

Diese DAO kümmert sich nur um die Zutat-Tabelle selbst. Die Junction-
Tabellen haben eigene DAOs (`artikel_zutat_dao.py`, später vom Bestell-
Team `wunsch_zutat_dao.py`).

Designentscheidungen:
  - Filter-Flags (`nur_verfuegbar`, `nur_vegetarisch`) sind Keyword-Only
    in `get_all()` zusammengefasst — statt für jede Kombination eine
    eigene Methode zu schreiben. Das hält die DAO klein und die UI
    flexibel: Wunschpizza-Builder kann z. B. `nur_verfuegbar=True`
    setzen, ein Allergie-Filter kommt später dazu.
  - Kein `commit()` in der DAO (gleicher Vertrag wie `kategorie_dao.py`).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Zutat


class ZutatDAO:
    """Persistenz-Operationen für `Zutat`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, zutat: Zutat) -> Zutat:
        """Speichert eine neue Zutat und gibt sie inkl. ID zurück.

        `flush()` + `refresh()` sorgen dafür, dass die generierte ID
        sofort am Objekt steht — der Service kann sie direkt z. B. an
        eine `ArtikelZutat`-Verknüpfung weitergeben.
        """
        session.add(zutat)
        session.flush()
        session.refresh(zutat)
        return zutat

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, zutat_id: int) -> Optional[Zutat]:
        """Lädt eine Zutat über ihre Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert. Die Service-
        Schicht entscheidet, ob daraus eine Exception oder eine UI-
        Meldung wird.
        """
        return session.get(Zutat, zutat_id)

    @staticmethod
    def get_by_name(session: Session, name: str) -> Optional[Zutat]:
        """Lädt eine Zutat über ihren Namen.

        Der Name ist im Modell `unique` — höchstens ein Treffer.
        Wird im Admin gebraucht, um Duplikate zu verhindern, und beim
        CSV-Import (z. B. „Mozzarella" einmal anlegen, dann referenzieren).
        """
        statement = select(Zutat).where(Zutat.name == name)
        return session.exec(statement).first()

    @staticmethod
    def get_all(
        session: Session,
        *,
        nur_verfuegbar: bool = False,
        nur_vegetarisch: bool = False,
        sortiert: bool = True,
    ) -> list[Zutat]:
        """Liefert Zutaten, optional gefiltert.

        Die Flags sind kumulativ:
          - `nur_verfuegbar=True` blendet ausverkaufte Zutaten aus
            (typisch im Wunschpizza-Builder, damit der Kunde nichts
            bestellen kann, was die Küche nicht hat).
          - `nur_vegetarisch=True` zeigt nur fleischfreie Zutaten —
            sinnvoll für einen späteren Allergie-/Diät-Filter.
          - `sortiert=True` ordnet alphabetisch nach Name (Default), für
            stabile Reihenfolge in UI und Tests.

        Keyword-Only erzwingt Lesbarkeit am Aufruf-Ort:
            ZutatDAO.get_all(session, nur_verfuegbar=True)
        statt
            ZutatDAO.get_all(session, True)  # was war True nochmal?
        """
        statement = select(Zutat)
        if nur_verfuegbar:
            statement = statement.where(Zutat.verfuegbar.is_(True))
        if nur_vegetarisch:
            statement = statement.where(Zutat.vegetarisch.is_(True))
        if sortiert:
            statement = statement.order_by(Zutat.name)
        return list(session.exec(statement).all())

    @staticmethod
    def exists(session: Session, name: str) -> bool:
        """Prüft, ob eine Zutat mit diesem Namen bereits existiert.

        Günstige Vorab-Prüfung im Service, damit `create()` nicht erst
        am UNIQUE-Constraint scheitert. Spart dem UI eine Exception.
        """
        return ZutatDAO.get_by_name(session, name) is not None

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, zutat: Zutat) -> Zutat:
        """Schreibt Änderungen einer bereits geladenen Zutat zurück.

        Erwartet, dass `zutat.id` gesetzt ist. SQLAlchemy erkennt das
        und macht ein UPDATE statt INSERT.

        Typische Updates: Preis ändern, Verfügbarkeit umschalten
        (z. B. „Heute keine frischen Pilze mehr").
        """
        session.add(zutat)
        session.flush()
        session.refresh(zutat)
        return zutat

    @staticmethod
    def verfuegbarkeit_setzen(
        session: Session, zutat_id: int, verfuegbar: bool
    ) -> Optional[Zutat]:
        """Schaltet die Verfügbarkeit einer Zutat um (Convenience-Methode).

        Häufiger Use-Case im Admin: „Mozzarella ausverkauft" — und es
        wäre Quatsch, dafür erst die ganze Zutat laden, mutieren und
        wieder speichern zu müssen. Diese Methode kapselt das in einem
        Aufruf. Gibt das aktualisierte Objekt zurück oder `None`, falls
        die ID nicht existiert.
        """
        zutat = session.get(Zutat, zutat_id)
        if zutat is None:
            return None
        zutat.verfuegbar = verfuegbar
        session.add(zutat)
        session.flush()
        session.refresh(zutat)
        return zutat

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, zutat_id: int) -> bool:
        """Löscht eine Zutat über ihre ID.

        Rückgabe:
          - True, falls eine Zutat gelöscht wurde
          - False, falls die ID nicht existierte

        Achtung: Eine Zutat, die in `artikel_zutat` oder `wunsch_zutat`
        referenziert wird, kann nicht gelöscht werden — der FK-Constraint
        wirft eine IntegrityError. Im Admin sollte man stattdessen
        `verfuegbarkeit_setzen(..., False)` benutzen.
        """
        zutat = session.get(Zutat, zutat_id)
        if zutat is None:
            return False
        session.delete(zutat)
        session.flush()
        return True
