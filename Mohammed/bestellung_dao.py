"""
DAO — Bestellung
=================
Datenbank-Zugriff für die Tabelle `bestellung`.

Eine Bestellung ist der Kopf-Datensatz einer Kunden-Bestellung. Die
einzelnen Artikel hängen als `Bestellposition` an der Bestellung (1:N) —
dafür gibt's die separate `BestellpositionDAO`.

Designentscheidungen:
  - Statische Methoden mit Session-Parameter (gleicher Stil wie
    `ArtikelDAO`). Damit kann der `BestellService` mehrere DAO-Aufrufe
    in EINER Transaktion machen — wichtig, weil das Speichern einer
    Bestellung aus mehreren Schritten besteht (Bestellung anlegen,
    Positionen anlegen, Zahlung anlegen, Quittung anlegen) und entweder
    alles oder nichts gespeichert werden muss.
  - Eager-Loading der `positionen`-Beziehung in `get_by_id_mit_positionen`,
    weil die UI fast immer auch die Positionen anzeigen will und wir
    nicht für jede Bestellung N+1-Queries auslösen wollen.
  - Kein `commit()` in der DAO (gleicher Vertrag wie die anderen DAOs
    im Younus-Stil).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from domain.models import Bestellposition, Bestellung, BestellStatus, WunschZutat


class BestellungDAO:
    """Persistenz-Operationen für `Bestellung`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, bestellung: Bestellung) -> Bestellung:
        """Speichert eine neue Bestellung und gibt sie inkl. ID zurück.

        `flush()` + `refresh()` befüllen die generierte ID sofort —
        wichtig, weil der `BestellService` direkt danach die zugehörigen
        `Bestellposition`-Einträge anlegen will und dafür die
        `bestellung_id` braucht.
        """
        session.add(bestellung)
        session.flush()
        session.refresh(bestellung)
        return bestellung

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, bestellung_id: int) -> Optional[Bestellung]:
        """Lädt eine Bestellung über ihre Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert. Lädt KEINE
        Positionen mit — dafür `get_by_id_mit_positionen()` nehmen.
        """
        return session.get(Bestellung, bestellung_id)

    @staticmethod
    def get_by_id_mit_positionen(
        session: Session, bestellung_id: int
    ) -> Optional[Bestellung]:
        """Lädt eine Bestellung inkl. aller Positionen und Wunsch-Zutaten.

        Eager-Loading:
          - Positionen mit ihrem Artikel
          - Positionen mit ihren Wunsch-Zutaten, jeweils mit der Zutat

        Damit die UI ohne weitere DB-Queries alle Daten anzeigen kann,
        auch wenn die Session inzwischen geschlossen ist (typisch bei
        NiceGUI, weil Render und DB-Zugriff zeitlich auseinanderdriften).
        """
        statement = (
            select(Bestellung)
            .where(Bestellung.id == bestellung_id)
            .options(
                # Artikel pro Position laden
                selectinload(Bestellung.positionen).selectinload(
                    Bestellposition.artikel
                ),
                # Wunsch-Zutaten pro Position laden, jeweils mit Zutat
                selectinload(Bestellung.positionen)
                .selectinload(Bestellposition.wunsch_zutaten)
                .selectinload(WunschZutat.zutat),
            )
        )
        return session.exec(statement).first()

    @staticmethod
    def alle_fuer_kunde(
        session: Session, kunden_id: int
    ) -> list[Bestellung]:
        """Liefert alle Bestellungen eines Kunden, neueste zuerst.

        Wird auf der `/bestellungen`-Seite verwendet (Irem), aber auch
        nach dem Checkout, wenn der Kunde seine gerade abgeschickte
        Bestellung sehen soll.

        Sortierung nach `bestellzeit DESC`: neue Bestellungen oben,
        damit der Kunde sie sofort findet.
        """
        statement = (
            select(Bestellung)
            .where(Bestellung.kunden_id == kunden_id)
            .order_by(Bestellung.bestellzeit.desc())
        )
        return list(session.exec(statement).all())

    @staticmethod
    def offene_bestellungen(session: Session) -> list[Bestellung]:
        """Alle Bestellungen, die noch nicht geliefert oder storniert sind.

        Für die Admin-/Mitarbeiter-Sicht: Welche Bestellungen muss die
        Küche noch bearbeiten, welche der Fahrer ausliefern?

        Sortierung: nach `bestellzeit ASC` — älteste zuerst, FIFO-Prinzip
        (wer zuerst bestellt hat, kriegt auch zuerst seine Pizza).
        """
        offene_status = [
            BestellStatus.OFFEN,
            BestellStatus.IN_BEARBEITUNG,
            BestellStatus.UNTERWEGS,
        ]
        statement = (
            select(Bestellung)
            .where(Bestellung.status.in_(offene_status))
            .order_by(Bestellung.bestellzeit)
        )
        return list(session.exec(statement).all())

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, bestellung: Bestellung) -> Bestellung:
        """Schreibt Änderungen einer bereits geladenen Bestellung zurück.

        Typische Updates:
          - `status` ändern (OFFEN -> IN_BEARBEITUNG -> UNTERWEGS ...)
          - `mitarbeiter_id` setzen, wenn ein Koch die Bestellung übernimmt
          - `gesamtbetrag` aktualisieren nach Neu-Berechnung
        """
        session.add(bestellung)
        session.flush()
        session.refresh(bestellung)
        return bestellung

    @staticmethod
    def status_setzen(
        session: Session, bestellung_id: int, status: BestellStatus
    ) -> Optional[Bestellung]:
        """Setzt den Status einer Bestellung neu (Convenience-Methode).

        Gibt das aktualisierte Objekt zurück oder `None`, falls die ID
        nicht existiert. Wird hauptsächlich vom Admin-Bereich benutzt,
        damit man nicht jedes Mal Laden -> Mutieren -> Speichern
        schreiben muss.
        """
        bestellung = session.get(Bestellung, bestellung_id)
        if bestellung is None:
            return None
        bestellung.status = status
        session.add(bestellung)
        session.flush()
        session.refresh(bestellung)
        return bestellung

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, bestellung_id: int) -> bool:
        """Löscht eine Bestellung.

        Rückgabe:
          - True, falls gelöscht
          - False, falls die ID nicht existierte

        Achtung: Im Produktionsbetrieb sollten Bestellungen NIE gelöscht
        werden — stattdessen `status_setzen(..., STORNIERT)`. Diese
        Methode existiert nur für Tests und das einheitliche CRUD-Schema
        aller DAOs.

        Wenn an der Bestellung noch Positionen, eine Zahlung oder eine
        Quittung hängen, schlägt das wegen FK-Constraint fehl — vorher
        aufräumen.
        """
        bestellung = session.get(Bestellung, bestellung_id)
        if bestellung is None:
            return False
        session.delete(bestellung)
        session.flush()
        return True
