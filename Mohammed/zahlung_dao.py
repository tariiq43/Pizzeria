"""
DAO — Zahlung
==============
Datenbank-Zugriff für die Tabelle `zahlung`.

Eine Zahlung gehört 1:1 zu einer Bestellung (`bestellung_id` ist im
Modell als `unique` markiert). Status-Flow:
    INITIALISIERT -> BEZAHLT
                  -> FEHLGESCHLAGEN

In unserer Schul-App ist die Zahlung gefakt (immer erfolgreich, siehe
`ZahlungService`). Aber das Schema ist so gebaut, dass man später echte
Zahlungs-Provider (Stripe, TWINT-API, ...) anbinden könnte, ohne die
DAO oder das Modell zu ändern.

Designentscheidung:
  - Statische Methoden mit Session-Parameter (gleicher Stil wie
    `ArtikelDAO` und `BestellungDAO`). Damit kann der `BestellService`
    die Zahlung in derselben Transaktion wie die Bestellung anlegen.
  - Kein `commit()` in der DAO.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Zahlung, ZahlungStatus


class ZahlungDAO:
    """Persistenz-Operationen für `Zahlung`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, zahlung: Zahlung) -> Zahlung:
        """Speichert eine neue Zahlung und gibt sie inkl. ID zurück.

        Achtung: `bestellung_id` ist unique. Eine zweite Zahlung für
        dieselbe Bestellung schlägt mit IntegrityError fehl — gewollt,
        weil pro Bestellung nur eine Zahlung existieren soll.
        """
        session.add(zahlung)
        session.flush()
        session.refresh(zahlung)
        return zahlung

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, zahlung_id: int) -> Optional[Zahlung]:
        """Lädt eine Zahlung über ihre Primary Key."""
        return session.get(Zahlung, zahlung_id)

    @staticmethod
    def finde_per_bestellung(
        session: Session, bestellung_id: int
    ) -> Optional[Zahlung]:
        """Liefert die Zahlung zu einer Bestellung (1:1-Beziehung).

        Wird vom `ZahlungService` benutzt, um vor dem Anlegen zu prüfen,
        ob die Bestellung schon eine Zahlung hat (Doppel-Erzeugung
        verhindern).
        """
        statement = select(Zahlung).where(
            Zahlung.bestellung_id == bestellung_id
        )
        return session.exec(statement).first()

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, zahlung: Zahlung) -> Zahlung:
        """Schreibt Änderungen einer bereits geladenen Zahlung zurück.

        Typischer Update: Status von INITIALISIERT auf BEZAHLT setzen,
        wenn die Bestätigung vom Zahlungs-Provider kommt.
        """
        session.add(zahlung)
        session.flush()
        session.refresh(zahlung)
        return zahlung

    @staticmethod
    def status_setzen(
        session: Session,
        zahlung_id: int,
        status: ZahlungStatus,
        transaktions_id: Optional[str] = None,
    ) -> Optional[Zahlung]:
        """Setzt den Status einer Zahlung (Convenience-Methode).

        Optional: `transaktions_id` mitsetzen, falls vom Zahlungs-
        Provider eine Referenz kommt (bei uns: die Fake-ID des
        `ZahlungService`).

        Gibt das aktualisierte Objekt zurück oder `None`, falls die ID
        nicht existiert.
        """
        zahlung = session.get(Zahlung, zahlung_id)
        if zahlung is None:
            return None
        zahlung.status = status
        if transaktions_id is not None:
            zahlung.transaktions_id = transaktions_id
        session.add(zahlung)
        session.flush()
        session.refresh(zahlung)
        return zahlung

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, zahlung_id: int) -> bool:
        """Löscht eine Zahlung.

        Nur für Tests sinnvoll — produktiv werden Zahlungen wegen
        Buchhaltung nie gelöscht. Gehört aber ins einheitliche CRUD-
        Schema aller DAOs.
        """
        zahlung = session.get(Zahlung, zahlung_id)
        if zahlung is None:
            return False
        session.delete(zahlung)
        session.flush()
        return True
