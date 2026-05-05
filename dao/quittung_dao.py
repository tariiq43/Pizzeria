"""
QuittungDAO — Pizzeria Sunshine
===============================
Datenzugriff für die Quittungen-Tabelle.

Eine Quittung wird erzeugt, sobald eine Bestellung erfolgreich bezahlt ist.
Sie speichert eine eindeutige Quittungsnummer, das Erstellungsdatum und
den Pfad zur generierten PDF-Datei.

Beziehung zur Bestellung: 1:1 — jede Bestellung hat genau eine Quittung,
und jede Quittung gehört zu genau einer Bestellung. bestellung_id ist im
Modell als unique markiert, doppeltes Erzeugen schlägt automatisch fehl.

Hinweis zur Aufbewahrung: Quittungen sind aus rechtlichen Gründen
unveränderlich (Aufbewahrungspflicht 10 Jahre in CH). delete() existiert
nur für Test-Zwecke — im Produktionscode bitte nicht aufrufen.
"""

from typing import List, Optional

from sqlmodel import select

from domain.models import Bestellung, Quittung
from utils.db import get_session


class QuittungDAO:
    """Data Access Object für Quittung-Entities."""

    # ----------------------------------------------------------------------
    # Standard-CRUD
    # ----------------------------------------------------------------------

    @staticmethod
    def create(quittung: Quittung) -> Quittung:
        """Speichert eine neue Quittung.

        Achtung: bestellung_id ist unique. Wenn schon eine Quittung für
        diese Bestellung existiert, wirft SQLite einen IntegrityError.
        Das ist gewollt — pro Bestellung darf es nur eine Quittung geben.
        Der QuittungService sollte vorher prüfen, ob bereits eine
        existiert (siehe finde_per_bestellung).
        """
        with get_session() as session:
            session.add(quittung)
            session.commit()
            session.refresh(quittung)
            return quittung

    @staticmethod
    def get_by_id(quittung_id: int) -> Optional[Quittung]:
        with get_session() as session:
            return session.get(Quittung, quittung_id)

    @staticmethod
    def update(quittung: Quittung) -> Quittung:
        """Aktualisiert eine bestehende Quittung.

        In der Praxis selten verwendet — Quittungen sind rechtlich
        unveränderlich. Ausnahme: pdf_pfad nachtragen, falls die PDF
        erst nach dem DB-Insert erzeugt wird.
        """
        with get_session() as session:
            session.add(quittung)
            session.commit()
            session.refresh(quittung)
            return quittung

    @staticmethod
    def delete(quittung_id: int) -> bool:
        """Löscht eine Quittung.

        WARNUNG: Im Produktionsbetrieb sollten Quittungen NIE gelöscht
        werden (Aufbewahrungspflicht). Diese Methode existiert nur für
        Tests und Entwicklung. Soll für die Präsentation drin bleiben,
        damit unsere DAOs alle dasselbe CRUD-Schema haben.
        """
        with get_session() as session:
            quittung = session.get(Quittung, quittung_id)
            if quittung is None:
                return False
            session.delete(quittung)
            session.commit()
            return True

    # ----------------------------------------------------------------------
    # Spezielle Queries
    # ----------------------------------------------------------------------

    @staticmethod
    def finde_per_bestellung(bestellung_id: int) -> Optional[Quittung]:
        """Liefert die Quittung zu einer Bestellung (1:1-Beziehung).

        Wird auf der /bestellungen-Seite verwendet, wenn der Kunde eine
        alte Quittung als PDF herunterladen will. Auch vom QuittungService,
        bevor eine neue Quittung erzeugt wird (Doppel-Erzeugung verhindern).
        """
        with get_session() as session:
            statement = select(Quittung).where(
                Quittung.bestellung_id == bestellung_id
            )
            return session.exec(statement).first()

    @staticmethod
    def finde_per_quittungsnummer(quittungsnummer: str) -> Optional[Quittung]:
        """Findet eine Quittung anhand ihrer Quittungsnummer.

        Quittungsnummern sind unique und werden vom QuittungService nach
        einem festen Schema generiert (z. B. "Q-2026-00042"). Wird z. B.
        für Audit-Anfragen oder Support-Cases gebraucht.
        """
        with get_session() as session:
            statement = select(Quittung).where(
                Quittung.quittungsnummer == quittungsnummer
            )
            return session.exec(statement).first()

    @staticmethod
    def alle_fuer_kunde(kunden_id: int) -> List[Quittung]:
        """Lädt alle Quittungen, die zu Bestellungen eines Kunden gehören.

        Wichtig: Wir joinen über Bestellung, weil Quittung selbst keinen
        direkten Bezug zum Kunden hat (kunden_id steckt in Bestellung).

        Sortierung: neueste zuerst — typische Bestellhistorie-Sicht.
        """
        with get_session() as session:
            statement = (
                select(Quittung)
                .join(Bestellung, Bestellung.id == Quittung.bestellung_id)
                .where(Bestellung.kunden_id == kunden_id)
                .order_by(Quittung.erstellt_am.desc())
            )
            return list(session.exec(statement).all())