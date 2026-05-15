"""
Tests — AuthService
====================
Service-Tests für Registrierung, Login und Passwort-Änderung.

Schwerpunkt:
  - Passwörter werden gehasht (NIE im Klartext in der DB).
  - Email wird normalisiert (klein + getrimmt) — sonst können sich
    zwei Konten mit „Anna@..." und „anna@..." anlegen lassen.
  - Login mit falschem Passwort liefert `None` (kein Exception).
  - Doppel-Registrierung mit derselben Email wirft `ValueError`.

Was hier NICHT getestet wird:
  - Die Session-Methoden (`session_setzen_kunde` etc.), weil die intern
    NiceGUI's `app.storage.user` benutzen — schwer ohne laufenden
    NiceGUI-Kontext zu testen. Diese Methoden sind dünn (zwei Zeilen)
    und werden in der End-to-End-Nutzung getestet.

Fixture-Hinweis:
  - `db_engine` (aus `conftest.py`) patcht `utils.db.engine` auf eine
    In-Memory-DB. AuthService benutzt `get_session()`, das intern
    automatisch die Test-Engine zieht — kein zusätzliches Monkeypatchen
    nötig.
"""

from __future__ import annotations

import pytest

from services.auth_service import AuthService


# ---------------------------------------------------------------------------
# Registrierung
# ---------------------------------------------------------------------------


def test_registrieren_kunde_erfolgreich(db_engine):
    """Eine neue Email kann erfolgreich registriert werden."""
    kunde = AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="geheim123",
    )

    assert kunde.id is not None
    assert kunde.email == "anna@beispiel.ch"
    # Passwort darf NIE im Klartext in der DB landen
    assert kunde.passwort_hash != "geheim123"
    assert len(kunde.passwort_hash) > 20  # bcrypt-Hash ist deutlich länger


def test_registrieren_kunde_email_wird_normalisiert(db_engine):
    """Eingabe „  ANNA@MAIL.CH " wird zu „anna@mail.ch" normalisiert."""
    kunde = AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="  ANNA@MAIL.CH ",
        passwort="geheim123",
    )

    assert kunde.email == "anna@mail.ch"


def test_registrieren_kunde_duplikat_wirft_value_error(db_engine):
    """Zweite Registrierung mit derselben Email schlägt fehl."""
    AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="geheim123",
    )

    with pytest.raises(ValueError):
        AuthService.registrieren_kunde(
            vorname="Andere",
            nachname="Person",
            email="anna@beispiel.ch",  # genau dieselbe Email
            passwort="anders456",
        )


def test_registrieren_kunde_duplikat_auch_bei_anderer_schreibweise(
    db_engine,
):
    """Email-Duplikat-Check ignoriert Groß-/Kleinschreibung."""
    AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="geheim123",
    )

    with pytest.raises(ValueError):
        AuthService.registrieren_kunde(
            vorname="Andere",
            nachname="Person",
            email="ANNA@BEISPIEL.CH",
            passwort="anders456",
        )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_kunde_korrekt(db_engine):
    """Mit richtigen Daten kommt das Kunden-Objekt zurück."""
    AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="geheim123",
    )

    kunde = AuthService.login_kunde("anna@beispiel.ch", "geheim123")

    assert kunde is not None
    assert kunde.email == "anna@beispiel.ch"


def test_login_kunde_falsches_passwort(db_engine):
    """Falsches Passwort → `None`, kein Exception."""
    AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="geheim123",
    )

    assert AuthService.login_kunde("anna@beispiel.ch", "falsch") is None


def test_login_kunde_unbekannte_email(db_engine):
    """Nicht-existente Email → `None`."""
    assert AuthService.login_kunde("niemand@nirgends.ch", "egal") is None


def test_login_kunde_funktioniert_mit_email_grossbuchstaben(db_engine):
    """Login akzeptiert auch „ANNA@..." (Email-Normalisierung beim Login)."""
    AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="geheim123",
    )

    kunde = AuthService.login_kunde("ANNA@BEISPIEL.CH", "geheim123")
    assert kunde is not None


# ---------------------------------------------------------------------------
# Passwort ändern
# ---------------------------------------------------------------------------


def test_passwort_aendern_kunde_erfolgreich(db_engine):
    """Nach Passwortänderung funktioniert das neue, nicht das alte."""
    kunde = AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="alt123",
    )

    AuthService.passwort_aendern_kunde(
        kunden_id=kunde.id,
        altes_passwort="alt123",
        neues_passwort="neu456",
    )

    # Altes Passwort funktioniert nicht mehr
    assert AuthService.login_kunde("anna@beispiel.ch", "alt123") is None
    # Neues Passwort funktioniert
    assert AuthService.login_kunde("anna@beispiel.ch", "neu456") is not None


def test_passwort_aendern_kunde_falsches_altes_passwort(db_engine):
    """Falsches altes Passwort → `ValueError`, Passwort bleibt unverändert."""
    kunde = AuthService.registrieren_kunde(
        vorname="Anna",
        nachname="Muster",
        email="anna@beispiel.ch",
        passwort="alt123",
    )

    with pytest.raises(ValueError):
        AuthService.passwort_aendern_kunde(
            kunden_id=kunde.id,
            altes_passwort="falsch",
            neues_passwort="neu456",
        )

    # Altes Passwort funktioniert noch
    assert AuthService.login_kunde("anna@beispiel.ch", "alt123") is not None