"""
Tests — QuittungDAO
====================
DB-Tests für die Quittungs-Persistenz.

Schwerpunkt:
  - `finde_per_bestellung` ist die Idempotenz-Grundlage für
    `QuittungService.quittung_erzeugen`. Funktioniert sie nicht, gibt's
    Doppel-Quittungen.
  - `finde_per_quittungsnummer` ist UI-relevant (Support-Cases:
    „Quittung Q-2026-00042").
  - `alle_fuer_kunde` macht einen JOIN über `Bestellung` — typische
    Stelle für N+1- oder Lookup-Bugs.

Die Tests legen jeweils eine minimale Bestellung mit Kunde + Adresse an,
damit die FK-Constraints zufrieden sind. Für Quittungs-Verhalten brauchen
wir keine Positionen — die werden in den Service-Tests abgedeckt.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from dao.adresse_dao import AdresseDAO
from dao.bestellung_dao import BestellungDAO
from dao.kunden_dao import KundenDAO
from dao.quittung_dao import QuittungDAO
from domain.models import (
    Adresse,
    BestellStatus,
    Bestellung,
    Kunde,
    Quittung,
)


# ---------------------------------------------------------------------------
# Setup-Helpers
# ---------------------------------------------------------------------------


def _minimal_setup(db_session) -> Bestellung:
    """Legt Kunde + Adresse + Bestellung an, gibt die Bestellung zurück.

    Sehr schlank — keine Positionen, keine Zahlung. Reicht, um den FK
    auf `bestellung_id` in `Quittung` zu befriedigen.
    """
    kunde = KundenDAO.create(
        db_session,
        Kunde(
            vorname="Anna",
            nachname="Muster",
            email="anna@beispiel.ch",
            passwort_hash="$2b$dummy",
        ),
    )
    adresse = AdresseDAO.create(
        db_session,
        Adresse(
            kunden_id=kunde.id,
            strasse="Hauptstrasse",
            hausnummer="1",
            plz="5000",
            ort="Aarau",
            ist_standard=True,
        ),
    )
    bestellung = BestellungDAO.create(
        db_session,
        Bestellung(
            kunden_id=kunde.id,
            lieferadresse_id=adresse.id,
            status=BestellStatus.OFFEN,
            gesamtbetrag=Decimal("38.50"),
            bestellzeit=datetime.now(),
        ),
    )
    return bestellung


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_und_finde_per_bestellung(db_session):
    """Eine erstellte Quittung ist über die Bestellung wiederfindbar."""
    bestellung = _minimal_setup(db_session)

    QuittungDAO.create(
        db_session,
        Quittung(
            bestellung_id=bestellung.id,
            quittungsnummer="Q-2026-00001",
            pdf_pfad="/tmp/quittung_Q-2026-00001.pdf",
        ),
    )

    treffer = QuittungDAO.finde_per_bestellung(db_session, bestellung.id)

    assert treffer is not None
    assert treffer.quittungsnummer == "Q-2026-00001"


def test_finde_per_bestellung_keine_quittung(db_session):
    """Bestellung ohne Quittung → `None`."""
    bestellung = _minimal_setup(db_session)
    assert QuittungDAO.finde_per_bestellung(db_session, bestellung.id) is None


def test_finde_per_quittungsnummer(db_session):
    """Lookup über die menschlich lesbare Quittungsnummer."""
    bestellung = _minimal_setup(db_session)
    QuittungDAO.create(
        db_session,
        Quittung(
            bestellung_id=bestellung.id,
            quittungsnummer="Q-2026-00042",
            pdf_pfad="/tmp/test.pdf",
        ),
    )

    treffer = QuittungDAO.finde_per_quittungsnummer(
        db_session, "Q-2026-00042"
    )

    assert treffer is not None
    assert treffer.bestellung_id == bestellung.id


def test_finde_per_quittungsnummer_unbekannt(db_session):
    """Unbekannte Quittungsnummer → `None`."""
    ergebnis = QuittungDAO.finde_per_quittungsnummer(
        db_session, "Q-1999-99999"
    )
    assert ergebnis is None


def test_alle_fuer_kunde_macht_join(db_session):
    """`alle_fuer_kunde` findet Quittungen über den JOIN auf Bestellung."""
    bestellung = _minimal_setup(db_session)
    QuittungDAO.create(
        db_session,
        Quittung(
            bestellung_id=bestellung.id,
            quittungsnummer="Q-2026-00001",
            pdf_pfad="/tmp/a.pdf",
        ),
    )

    treffer = QuittungDAO.alle_fuer_kunde(db_session, bestellung.kunden_id)

    assert len(treffer) == 1
    assert treffer[0].quittungsnummer == "Q-2026-00001"