"""
DAO — Bestellposition
======================
Datenbank-Zugriff für die Tabelle `bestellposition` und die zugehörige
Junction-Tabelle `wunsch_zutat`.

Eine Bestellposition ist eine Zeile einer Bestellung (z. B. „2x Pizza
Salami"). Wenn `ist_wunschpizza=True` ist, hängen über die Junction-
Tabelle `wunsch_zutat` die individuell gewählten Zutaten dran.

Designentscheidung — beide Tabellen in einer DAO:
  `wunsch_zutat` macht ohne `bestellposition` keinen Sinn (FK-Beziehung,
  und fachlich gehört es zusammen). Eine separate `WunschZutatDAO` wäre
  möglich, aber für das Schulprojekt unnötiger Overhead. Falls das Team
  später mehr Komplexität braucht, kann man die Klasse leicht aufteilen.

  Younus hat seine Junction-Tabelle (`ArtikelZutat`) auch in einer eigenen
  DAO — bei ihm gibt's aber mehr Operationen (Rezept setzen, Menge
  aktualisieren, etc.). Bei `WunschZutat` brauche ich nur „hinzufügen“
  und „alle laden“, deshalb passt es hier rein.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from domain.models import Bestellposition, WunschZutat


class BestellpositionDAO:
    """Persistenz-Operationen für `Bestellposition` und `WunschZutat`."""

    # =======================================================================
    # Bestellposition — CRUD
    # =======================================================================

    @staticmethod
    def create(session: Session, position: Bestellposition) -> Bestellposition:
        """Speichert eine neue Bestellposition.

        `flush()` + `refresh()` setzen die generierte ID — wichtig, weil
        der `BestellService` direkt danach die Wunsch-Zutaten anlegen
        will und dafür die `bestellposition_id` braucht.
        """
        session.add(position)
        session.flush()
        session.refresh(position)
        return position

    @staticmethod
    def get_by_id(
        session: Session, position_id: int
    ) -> Optional[Bestellposition]:
        """Lädt eine Bestellposition über ihre Primary Key."""
        return session.get(Bestellposition, position_id)

    @staticmethod
    def alle_fuer_bestellung(
        session: Session, bestellung_id: int
    ) -> list[Bestellposition]:
        """Liefert alle Positionen einer Bestellung, mit Artikel und
        Wunsch-Zutaten eager-loaded.

        Damit die UI Name/Preis und die gewählten Zutaten direkt anzeigen
        kann, ohne dass die Session noch offen sein muss.

        Sortierung nach ID (= Reihenfolge des Hinzufügens). Bei Bedarf
        könnte man auch nach Artikel-Name sortieren, aber die natürliche
        Reihenfolge ist intuitiver — der Kunde sieht seine Pizza so,
        wie er sie eingegeben hat.
        """
        statement = (
            select(Bestellposition)
            .where(Bestellposition.bestellung_id == bestellung_id)
            .options(
                selectinload(Bestellposition.artikel),
                selectinload(Bestellposition.wunsch_zutaten).selectinload(
                    WunschZutat.zutat
                ),
            )
            .order_by(Bestellposition.id)
        )
        return list(session.exec(statement).all())

    @staticmethod
    def delete(session: Session, position_id: int) -> bool:
        """Löscht eine Bestellposition.

        Wird im Produktivbetrieb fast nie gebraucht (Bestellungen sind
        unveränderlich), aber praktisch für Tests und für das Aufräumen
        beim Storno einer Bestellung in der Entwicklung.

        Achtung: Wunsch-Zutaten zu dieser Position werden vorher manuell
        entfernt — wir lassen die DB nicht stillschweigend cascaden,
        damit fehlerhafte Aufrufe nicht halbe Datensätze hinterlassen.
        """
        position = session.get(Bestellposition, position_id)
        if position is None:
            return False
        # Erst Wunsch-Zutaten, dann Position selbst (FK-Reihenfolge)
        BestellpositionDAO.wunsch_zutaten_loeschen(session, position_id)
        session.delete(position)
        session.flush()
        return True

    # =======================================================================
    # WunschZutat — Junction zwischen Bestellposition und Zutat
    # =======================================================================

    @staticmethod
    def wunsch_zutat_hinzufuegen(
        session: Session,
        bestellposition_id: int,
        zutat_id: int,
        menge: Decimal = Decimal("1"),
    ) -> WunschZutat:
        """Fügt einer Wunschpizza eine gewählte Zutat hinzu.

        Strikt: Wenn die Kombination (`bestellposition_id`, `zutat_id`)
        bereits existiert, lässt der Composite Primary Key den INSERT
        scheitern und SQLAlchemy wirft eine IntegrityError. Das ist
        gewollt — dieselbe Zutat zweimal auf eine Pizza zu legen, ergibt
        keinen Sinn (wer mehr will, erhöht die `menge`).
        """
        eintrag = WunschZutat(
            bestellposition_id=bestellposition_id,
            zutat_id=zutat_id,
            menge=menge,
        )
        session.add(eintrag)
        session.flush()
        session.refresh(eintrag)
        return eintrag

    @staticmethod
    def wunsch_zutaten_laden(
        session: Session, bestellposition_id: int
    ) -> list[WunschZutat]:
        """Liefert alle Wunsch-Zutaten einer Bestellposition.

        Eager-Loading der `Zutat`-Relation, damit der Aufrufer
        `eintrag.zutat.name` lesen kann, ohne dass die Session noch
        offen sein muss.
        """
        statement = (
            select(WunschZutat)
            .where(WunschZutat.bestellposition_id == bestellposition_id)
            .options(selectinload(WunschZutat.zutat))
            .order_by(WunschZutat.zutat_id)
        )
        return list(session.exec(statement).all())

    @staticmethod
    def wunsch_zutaten_loeschen(
        session: Session, bestellposition_id: int
    ) -> int:
        """Entfernt alle Wunsch-Zutaten einer Bestellposition.

        Rückgabe: Anzahl der entfernten Einträge.

        Wird beim Löschen einer Bestellposition aufgerufen — ohne das
        hingen verwaiste Wunsch-Zutaten in der DB rum, und der FK-
        Constraint würde das eigentliche `DELETE` der Bestellposition
        blockieren.
        """
        eintraege = BestellpositionDAO.wunsch_zutaten_laden(
            session, bestellposition_id
        )
        for eintrag in eintraege:
            session.delete(eintrag)
        session.flush()
        return len(eintraege)
