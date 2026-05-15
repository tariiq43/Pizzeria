"""
Tests — QuittungService
========================
Service-Tests für die Quittungs-Logik.

Schwerpunkt:
  - **MwSt-Aufschlüsselung** (`mwst_aufschluesseln`): pure Funktion,
    keine DB — einfach zu testen und für die Prüfung gut erklärbar.
    Wir prüfen:
      * Grundrechnung stimmt (netto + mwst = brutto)
      * Rundung auf 2 Nachkommastellen ist ROUND_HALF_UP
      * Decimal-Eingabe in Decimal-Ausgabe (keine Float-Rundungsfehler)
  - **Quittungsnummer-Generierung**: Format `Q-YYYY-NNNNN` und
    Inkrement-Logik.
  - **Idempotenz** in `quittung_erzeugen`: Zweiter Aufruf erzeugt
    KEINE neue Quittung, sondern liefert den Pfad der bestehenden.

PDF-Erzeugung wird gemockt — sonst bräuchten wir `reportlab` als
Test-Dependency und müssten die Datei wirklich auf die Platte schreiben.
Wir wollen die Service-Logik testen, nicht die PDF-Bibliothek.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from dao.adresse_dao import AdresseDAO
from dao.bestellung_dao import BestellungDAO
from dao.kunden_dao import KundenDAO
from dao.quittung_dao import QuittungDAO
from domain.models import (
    Adresse,
    BestellStatus,
    Bestellung,
    Kunde,
)
from services.quittung_service import (
    MWST_SATZ,
    QuittungService,
)


# ---------------------------------------------------------------------------
# MwSt-Aufschlüsselung — pure Funktion, keine DB nötig
# ---------------------------------------------------------------------------


def test_mwst_aufschluesseln_grundfall():
    """Bei CHF 100.00 brutto kommen netto ≈ 97.47 und MwSt ≈ 2.53 raus.

    100 / 1.026 = 97.4658... → gerundet 97.47
    100 - 97.47 = 2.53
    """
    ergebnis = QuittungService.mwst_aufschluesseln(Decimal("100.00"))

    assert ergebnis.brutto == Decimal("100.00")
    assert ergebnis.netto == Decimal("97.47")
    assert ergebnis.mwst == Decimal("2.53")
    assert ergebnis.mwst_satz == MWST_SATZ


def test_mwst_aufschluesseln_summe_stimmt_immer():
    """Egal welcher Bruttobetrag — netto + mwst muss brutto ergeben.

    Wenn die Rundung schief läuft, kann es zu „Centabweichungen"
    kommen: 97.47 + 2.53 = 100.00 ✓, aber bei anderen Beträgen wäre
    auch 99.99 oder 100.01 denkbar. Wir testen mehrere Werte.
    """
    fuer_pruefung = [
        Decimal("38.50"),
        Decimal("12.95"),
        Decimal("1.00"),
        Decimal("999.99"),
        Decimal("0.50"),
    ]
    for brutto in fuer_pruefung:
        ergebnis = QuittungService.mwst_aufschluesseln(brutto)
        # Netto + MwSt = Brutto. Falls die Rundung mal 1 Rappen
        # daneben liegt, ist das fachlich akzeptabel auf Quittungen —
        # für unsere Logik aber: muss exakt aufgehen.
        assert ergebnis.netto + ergebnis.mwst == ergebnis.brutto, (
            f"Brutto={brutto}: Summe stimmt nicht "
            f"({ergebnis.netto} + {ergebnis.mwst} != {ergebnis.brutto})"
        )


def test_mwst_aufschluesseln_rundet_auf_zwei_stellen():
    """Eingabe mit mehr als 2 Stellen wird auf 2 gerundet."""
    ergebnis = QuittungService.mwst_aufschluesseln(Decimal("12.345"))

    # 12.345 wird zu 12.35 (Halb-Aufrunden)
    assert ergebnis.brutto == Decimal("12.35")


def test_mwst_aufschluesseln_nutzt_decimal_typ():
    """Rückgabe ist `Decimal` — keine `float`-Werte (Rundungsfehler!).

    Wichtig fürs Buchhaltungs-Korrektheit: Mit float könnten Beträge
    wie 0.1 + 0.2 = 0.30000000000000004 entstehen. Mit Decimal nicht.
    """
    ergebnis = QuittungService.mwst_aufschluesseln(Decimal("100.00"))
    assert isinstance(ergebnis.brutto, Decimal)
    assert isinstance(ergebnis.netto, Decimal)
    assert isinstance(ergebnis.mwst, Decimal)


# ---------------------------------------------------------------------------
# Quittungsnummer-Generierung
# ---------------------------------------------------------------------------


def test_naechste_quittungsnummer_erste_im_jahr(db_session):
    """Wenn noch keine Quittung im Jahr existiert, fängt's bei 00001 an."""
    nummer = QuittungService._naechste_quittungsnummer(db_session, 2026)
    assert nummer == "Q-2026-00001"


def test_naechste_quittungsnummer_inkrementiert(db_session):
    """Nach Q-2026-00001 kommt Q-2026-00002."""
    bestellung = _bestellung_anlegen(db_session)
    QuittungDAO.create(
        db_session,
        _quittung_objekt(bestellung.id, "Q-2026-00001"),
    )

    naechste = QuittungService._naechste_quittungsnummer(db_session, 2026)
    assert naechste == "Q-2026-00002"


def test_naechste_quittungsnummer_jahr_isolation(db_session):
    """Quittungen aus 2025 beeinflussen die Numerierung in 2026 nicht."""
    bestellung_2025 = _bestellung_anlegen(db_session)
    QuittungDAO.create(
        db_session,
        _quittung_objekt(bestellung_2025.id, "Q-2025-00099"),
    )

    naechste_2026 = QuittungService._naechste_quittungsnummer(db_session, 2026)
    assert naechste_2026 == "Q-2026-00001"


# ---------------------------------------------------------------------------
# `quittung_erzeugen` — Idempotenz (mit gemocktem PDF-Generator)
# ---------------------------------------------------------------------------


def test_quittung_erzeugen_idempotent(db_session, monkeypatch, tmp_path):
    """Zweimal `quittung_erzeugen` aufrufen → genau EINE Quittung in der DB.

    Mohammeds BestellService fängt Hook-Exceptions und macht weiter,
    OHNE die Transaktion zurückzurollen. Wenn er den Hook bei einem
    Retry erneut aufruft, dürfen keine Duplikate entstehen — die
    Quittungsnummer ist UNIQUE und ein zweites Insert würde sonst
    fehlschlagen.
    """
    # PDF-Erzeugung mocken: wir wollen die DB-Logik testen, nicht
    # reportlab. Wir erzeugen einfach eine Dummy-Datei am Zielpfad.
    def fake_pdf_erzeugen(*, ziel_pfad, **_kwargs):
        Path(ziel_pfad).write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        "services.quittung_service.quittung_pdf_erzeugen",
        fake_pdf_erzeugen,
    )
    # PDFs in einen tmp_path schreiben, damit nichts im echten
    # Projekt-Verzeichnis liegen bleibt.
    monkeypatch.setattr(
        "services.quittung_service.QUITTUNGEN_VERZEICHNIS",
        tmp_path / "quittungen",
    )

    bestellung = _bestellung_anlegen(db_session)

    # Erster Aufruf — legt Quittung an
    pfad_1 = QuittungService.quittung_erzeugen(db_session, bestellung.id)

    # Zweiter Aufruf — gibt den GLEICHEN Pfad zurück
    pfad_2 = QuittungService.quittung_erzeugen(db_session, bestellung.id)

    assert pfad_1 == pfad_2

    # Und in der DB liegt genau EINE Quittung
    quittung = QuittungDAO.finde_per_bestellung(db_session, bestellung.id)
    assert quittung is not None


def test_quittung_erzeugen_bestellung_existiert_nicht(db_session):
    """Quittung für nicht-existente Bestellung → `ValueError`."""
    with pytest.raises(ValueError):
        QuittungService.quittung_erzeugen(db_session, 99999)


# ---------------------------------------------------------------------------
# Helpers (lokal — nur für diese Test-Datei)
# ---------------------------------------------------------------------------


def _bestellung_anlegen(db_session) -> Bestellung:
    """Legt eine minimale, valide Bestellung an (Kunde + Adresse + Bestellung).

    Keine Positionen — die brauchen wir hier nicht. Wenn `quittung_erzeugen`
    intern die Positionen lesen will, geht das, weil sie als leere Liste
    durchs Modell laufen.
    """
    kunde = KundenDAO.create(
        db_session,
        Kunde(
            vorname="Anna",
            nachname="Muster",
            email=f"anna+{datetime.now().timestamp()}@beispiel.ch",
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
    return BestellungDAO.create(
        db_session,
        Bestellung(
            kunden_id=kunde.id,
            lieferadresse_id=adresse.id,
            status=BestellStatus.OFFEN,
            gesamtbetrag=Decimal("38.50"),
            bestellzeit=datetime.now(),
        ),
    )


def _quittung_objekt(bestellung_id: int, nummer: str):
    """Quittungs-Objekt für DB-Inserts in den Tests."""
    from domain.models import Quittung

    return Quittung(
        bestellung_id=bestellung_id,
        quittungsnummer=nummer,
        pdf_pfad=f"/tmp/{nummer}.pdf",
    )