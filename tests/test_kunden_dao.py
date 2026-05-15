"""
Tests — KundenDAO
==================
Direkte DB-Tests für die Persistenz-Schicht der Kunden.

Was hier getestet wird:
  - CRUD-Operationen funktionieren grundsätzlich.
  - `finde_per_email` normalisiert (lowercase + trim), bevor sie sucht
    — das ist eine DAO-Regel, die in der gesamten App relevant ist
    (z. B. Login mit „Test@Mail.com" muss „test@mail.com" finden).
  - `None` wird sauber zurückgegeben bei „nicht gefunden" (kein Exception-
    Throwing für triviale Lookup-Fehler).

Was hier NICHT getestet wird:
  - SQL-Generierung — das ist SQLAlchemys Job, nicht unserer.
  - Performance — bei einer Schul-DB irrelevant.
"""

from __future__ import annotations

from dao.kunden_dao import KundenDAO
from domain.models import Kunde


# Hilfsfunktion: Kunde-Objekt mit sinnvollen Defaults bauen, ohne dass
# jeder Test die Felder einzeln aufzählt. Bewusst hier statt in
# conftest.py, weil die Helper nur diese DAO-Tests betreffen.
def _kunde(
    email: str = "anna@beispiel.ch",
    vorname: str = "Anna",
    nachname: str = "Muster",
    passwort_hash: str = "$2b$dummy",
    telefon: str | None = None,
) -> Kunde:
    return Kunde(
        vorname=vorname,
        nachname=nachname,
        email=email,
        passwort_hash=passwort_hash,
        telefon=telefon,
    )


def test_create_und_get_by_id(db_session):
    """Ein erstellter Kunde lässt sich anschließend per ID laden."""
    kunde = KundenDAO.create(db_session, _kunde())

    geladen = KundenDAO.get_by_id(db_session, kunde.id)

    assert geladen is not None
    assert geladen.email == "anna@beispiel.ch"
    assert geladen.id == kunde.id


def test_get_by_id_nicht_existent(db_session):
    """Bei nicht-existenter ID kommt `None` zurück — keine Exception."""
    ergebnis = KundenDAO.get_by_id(db_session, 99999)
    assert ergebnis is None


def test_finde_per_email_grossschreibung_und_leerzeichen(db_session):
    """Email-Normalisierung: Großschreibung und Leerzeichen werden ignoriert.

    Wichtig, weil das eine geteilte Erwartung zwischen AuthService
    (Registrierung speichert lowercase) und Login (sucht mit beliebiger
    Schreibweise) ist.
    """
    KundenDAO.create(db_session, _kunde(email="anna@beispiel.ch"))

    # Suche mit „verfälschter" Eingabe
    treffer = KundenDAO.finde_per_email(db_session, "  ANNA@Beispiel.CH  ")

    assert treffer is not None
    assert treffer.email == "anna@beispiel.ch"


def test_finde_per_email_nicht_existent(db_session):
    """Unbekannte Email → `None`."""
    ergebnis = KundenDAO.finde_per_email(db_session, "niemand@nirgends.ch")
    assert ergebnis is None


def test_update_aendert_felder(db_session):
    """Update schreibt geänderte Felder in die DB zurück."""
    kunde = KundenDAO.create(db_session, _kunde(vorname="Anna"))

    kunde.vorname = "Annika"
    KundenDAO.update(db_session, kunde)

    erneut_geladen = KundenDAO.get_by_id(db_session, kunde.id)
    assert erneut_geladen is not None
    assert erneut_geladen.vorname == "Annika"


def test_delete_entfernt_zeile(db_session):
    """Nach Delete liefert get_by_id `None`."""
    kunde = KundenDAO.create(db_session, _kunde())

    geloescht = KundenDAO.delete(db_session, kunde.id)

    assert geloescht is True
    assert KundenDAO.get_by_id(db_session, kunde.id) is None


def test_delete_nicht_existent_gibt_false(db_session):
    """Delete auf unbekannte ID gibt `False` — keine Exception."""
    assert KundenDAO.delete(db_session, 99999) is False