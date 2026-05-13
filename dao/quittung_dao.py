"""
DAO — Quittung
===============
Datenbank-Zugriff für die Tabelle `quittung`.

Eine Quittung wird erzeugt, sobald eine Bestellung erfolgreich bezahlt
ist. Sie speichert eine eindeutige Quittungsnummer, das Erstellungsdatum
und den Pfad zur generierten PDF-Datei.

Beziehung zur Bestellung: 1:1 — jede Bestellung hat genau eine Quittung,
und jede Quittung gehört zu genau einer Bestellung. `bestellung_id` ist
im Modell als `unique` markiert, doppeltes Erzeugen schlägt automatisch
fehl.

Hinweis zur Aufbewahrung: Quittungen sind aus rechtlichen Gründen
unveränderlich (Aufbewahrungspflicht 10 Jahre in CH). `delete()` existiert
nur für Test-Zwecke — im Produktionscode bitte nicht aufrufen. Bleibt
trotzdem dabei, damit alle DAOs dasselbe CRUD-Schema haben (gleicher
Vertrag wie die anderen DAOs).

Designentscheidungen:
  - `alle_fuer_kunde()` joint über `Bestellung`, weil `Quittung` keinen
    direkten `kunden_id`-FK hat. Das hält das Schema schlank (Kunde steht
    nur in Bestellung), kostet uns hier aber eine Zeile JOIN-Logik.
  - `finde_per_quittungsnummer()` ist eigene Methode, weil die Quittungs-
    nummer nach einem festen Schema („Q-2026-00042") generiert wird und
    auf Quittungen + Support-Cases referenziert wird.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Bestellung, Quittung


class QuittungDAO:
    """Persistenz-Operationen für `Quittung`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, quittung: Quittung) -> Quittung:
        """Speichert eine neue Quittung und gibt sie inkl. ID zurück.

        `flush()` + `refresh()` setzen die generierte Primary-Key-ID
        sofort. Der `QuittungService` braucht die ID anschliessend, um
        die PDF zu erzeugen und den Pfad zurückzuschreiben.

        Achtung: `bestellung_id` ist `unique`. Wenn schon eine Quittung
        für diese Bestellung existiert, wirft SQLite eine IntegrityError —
        das ist gewollt (pro Bestellung höchstens eine Quittung). Der
        Service prüft vorher mit `finde_per_bestellung()` und entscheidet,
        ob es ein Fehler ist oder die alte Quittung zurückgegeben wird.
        """
        session.add(quittung)
        session.flush()
        session.refresh(quittung)
        return quittung

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, quittung_id: int) -> Optional[Quittung]:
        """Lädt eine Quittung über ihre Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert.
        """
        return session.get(Quittung, quittung_id)

    @staticmethod
    def finde_per_bestellung(
        session: Session, bestellung_id: int
    ) -> Optional[Quittung]:
        """Liefert die Quittung zu einer Bestellung (1:1-Beziehung).

        Wird auf der `/bestellungen`-Seite verwendet, wenn der Kunde eine
        alte Quittung als PDF herunterladen will. Auch vom `QuittungService`,
        bevor eine neue Quittung erzeugt wird (Doppel-Erzeugung
        verhindern).
        """
        statement = select(Quittung).where(
            Quittung.bestellung_id == bestellung_id
        )
        return session.exec(statement).first()

    @staticmethod
    def finde_per_quittungsnummer(
        session: Session, quittungsnummer: str
    ) -> Optional[Quittung]:
        """Findet eine Quittung anhand ihrer Quittungsnummer.

        Quittungsnummern sind `unique` und werden vom `QuittungService`
        nach einem festen Schema generiert (z. B. „Q-2026-00042"). Wird
        z. B. für Audit-Anfragen oder Support-Cases gebraucht — der
        Kunde schreibt seine Quittungsnummer in den Support-Chat, und
        der Mitarbeiter findet die Bestellung darüber sofort.
        """
        statement = select(Quittung).where(
            Quittung.quittungsnummer == quittungsnummer
        )
        return session.exec(statement).first()

    @staticmethod
    def alle_fuer_kunde(session: Session, kunden_id: int) -> list[Quittung]:
        """Lädt alle Quittungen, die zu Bestellungen eines Kunden gehören.

        Wichtig: Wir joinen über `Bestellung`, weil `Quittung` selbst
        keinen direkten Bezug zum Kunden hat (`kunden_id` steckt nur in
        `Bestellung`). Die Verknüpfung ist über `bestellung_id` aber
        eindeutig.

        Sortierung: neueste zuerst (`erstellt_am DESC`) — typische
        Bestellhistorie-Sicht im Kundenkonto.
        """
        statement = (
            select(Quittung)
            .join(Bestellung, Bestellung.id == Quittung.bestellung_id)
            .where(Bestellung.kunden_id == kunden_id)
            .order_by(Quittung.erstellt_am.desc())
        )
        return list(session.exec(statement).all())

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, quittung: Quittung) -> Quittung:
        """Schreibt Änderungen einer bereits geladenen Quittung zurück.

        Erwartet, dass `quittung.id` gesetzt ist. SQLAlchemy erkennt das
        und macht ein UPDATE statt INSERT.

        In der Praxis selten verwendet — Quittungen sind rechtlich
        unveränderlich. Ausnahme: `pdf_pfad` nachtragen, falls die PDF
        erst nach dem DB-Insert erzeugt wird (typischer Ablauf im
        `QuittungService`).
        """
        session.add(quittung)
        session.flush()
        session.refresh(quittung)
        return quittung

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, quittung_id: int) -> bool:
        """Löscht eine Quittung über ihre ID.

        Rückgabe:
          - True, falls eine Quittung gelöscht wurde
          - False, falls die ID nicht existierte

        WARNUNG: Im Produktionsbetrieb sollten Quittungen NIE gelöscht
        werden (Aufbewahrungspflicht 10 Jahre). Diese Methode existiert
        nur für Tests und Entwicklung — siehe Modul-Docstring.
        """
        quittung = session.get(Quittung, quittung_id)
        if quittung is None:
            return False
        session.delete(quittung)
        session.flush()
        return True