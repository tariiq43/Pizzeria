"""
Tests — AdresseDAO
===================
DB-Tests für die Persistenz-Schicht der Adressen.

Schwerpunkt:
  - Adressen sind 1:N zu einem Kunden (eine Person, mehrere Adressen).
  - Eine Adresse pro Kunde ist als „Standard" markiert (Flag `ist_standard`).
  - Die DAO weiß NICHT, dass nur eine Adresse Standard sein darf —
    das ist Service-Regel. Sie liefert nur „die Standard-Adresse" oder
    `None`. Wenn der Service zwei als Standard markiert (Bug),
    bekommen wir hier eine — dann hätte der Service einen Fehler.
"""

from __future__ import annotations

from dao.adresse_dao import AdresseDAO
from dao.kunden_dao import KundenDAO
from domain.models import Adresse, Kunde


# Hilfsfunktionen (lokal — nicht in conftest, weil nur hier verwendet)


def _kunde_anlegen(db_session) -> Kunde:
    """Legt einen Test-Kunden in der DB an und gibt ihn zurück."""
    return KundenDAO.create(
        db_session,
        Kunde(
            vorname="Anna",
            nachname="Muster",
            email="anna@beispiel.ch",
            passwort_hash="$2b$dummy",
        ),
    )


def _adresse(
    kunden_id: int,
    strasse: str = "Hauptstrasse",
    hausnummer: str = "1",
    plz: str = "5000",
    ort: str = "Aarau",
    ist_standard: bool = False,
) -> Adresse:
    return Adresse(
        kunden_id=kunden_id,
        strasse=strasse,
        hausnummer=hausnummer,
        plz=plz,
        ort=ort,
        ist_standard=ist_standard,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_und_get_by_id(db_session):
    """Erstellte Adresse lässt sich per ID wiederfinden."""
    kunde = _kunde_anlegen(db_session)
    adresse = AdresseDAO.create(db_session, _adresse(kunde.id))

    geladen = AdresseDAO.get_by_id(db_session, adresse.id)

    assert geladen is not None
    assert geladen.strasse == "Hauptstrasse"
    assert geladen.kunden_id == kunde.id


def test_alle_fuer_kunde(db_session):
    """Liefert alle Adressen eines Kunden, andere Kunden werden ignoriert."""
    kunde_a = _kunde_anlegen(db_session)
    kunde_b = KundenDAO.create(
        db_session,
        Kunde(
            vorname="Bea",
            nachname="Beispiel",
            email="bea@beispiel.ch",
            passwort_hash="$2b$dummy",
        ),
    )

    AdresseDAO.create(db_session, _adresse(kunde_a.id, strasse="A1"))
    AdresseDAO.create(db_session, _adresse(kunde_a.id, strasse="A2"))
    AdresseDAO.create(db_session, _adresse(kunde_b.id, strasse="B1"))

    fuer_a = AdresseDAO.alle_fuer_kunde(db_session, kunde_a.id)

    assert len(fuer_a) == 2
    strassen = {a.strasse for a in fuer_a}
    assert strassen == {"A1", "A2"}


def test_standard_adresse_wird_gefunden(db_session):
    """`standard_adresse` liefert genau die als Standard markierte Adresse."""
    kunde = _kunde_anlegen(db_session)
    AdresseDAO.create(
        db_session, _adresse(kunde.id, strasse="Hinten", ist_standard=False)
    )
    AdresseDAO.create(
        db_session, _adresse(kunde.id, strasse="Vorne", ist_standard=True)
    )

    standard = AdresseDAO.standard_adresse(db_session, kunde.id)

    assert standard is not None
    assert standard.strasse == "Vorne"


def test_standard_adresse_keine_vorhanden(db_session):
    """Wenn keine Adresse Standard ist, kommt `None` zurück."""
    kunde = _kunde_anlegen(db_session)
    AdresseDAO.create(db_session, _adresse(kunde.id, ist_standard=False))

    assert AdresseDAO.standard_adresse(db_session, kunde.id) is None


def test_delete_entfernt_adresse(db_session):
    """Adresse löschen entfernt sie aus der DB."""
    kunde = _kunde_anlegen(db_session)
    adresse = AdresseDAO.create(db_session, _adresse(kunde.id))

    geloescht = AdresseDAO.delete(db_session, adresse.id)

    assert geloescht is True
    assert AdresseDAO.get_by_id(db_session, adresse.id) is None