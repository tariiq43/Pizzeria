"""
Tests — BestellService
=======================
Einfache pytest-Tests für die Warenkorb-Logik und den Bestell-Flow.

Strategie:
  - Warenkorb-Tests laufen rein im Speicher und brauchen keine DB —
    wir mocken Artikel/Zutat-Lookups, indem wir vorher Test-Daten in
    die echte SQLite anlegen. Für ein Studienprojekt ok.
  - Wir verwenden eine temporäre DB pro Test (siehe `tmp_db`-Fixture),
    damit Tests sich nicht gegenseitig beeinflussen.

Wenn du die Tests laufen lassen willst:
    pytest tests/test_bestell_service.py -v
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event

import utils.db as db_module  # damit wir die Engine umbiegen können
from domain.models import (
    Adresse,
    Artikel,
    BestellStatus,
    Kategorie,
    Kunde,
    ZahlungStatus,
    Zutat,
)
from services.bestell_service import BestellService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    """Erzeugt eine frische SQLite-DB pro Test und biegt die globale
    Engine darauf um.

    Damit ist jeder Test isoliert — keine Reste von vorigen Tests, kein
    Konflikt mit der echten `pizzeria.db`.
    """
    db_pfad = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_pfad}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # FK-Constraints aktivieren (analog zu utils/db.py)
    @event.listens_for(test_engine, "connect")
    def _fk_an(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Globale Engine im utils-Modul ersetzen, damit get_session() unsere
    # Test-Engine benutzt.
    monkeypatch.setattr(db_module, "engine", test_engine)

    # Schema anlegen
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    # Cleanup macht tmp_path automatisch


@pytest.fixture
def basis_daten(tmp_db):
    """Legt einen Kunden, eine Adresse, eine Kategorie, eine Pizza und
    zwei Zutaten an. Gibt die IDs als Dict zurück.

    Damit haben Tests etwas zum Bestellen, ohne den Setup-Code zu
    wiederholen.
    """
    with Session(tmp_db) as s:
        kunde = Kunde(
            vorname="Max",
            nachname="Muster",
            email="max@example.com",
            passwort_hash="x",
        )
        s.add(kunde)
        s.commit()
        s.refresh(kunde)

        adresse = Adresse(
            kunden_id=kunde.id,
            strasse="Musterstrasse",
            hausnummer="1",
            plz="3000",
            ort="Bern",
            ist_standard=True,
        )
        s.add(adresse)

        kategorie = Kategorie(name="Pizza", sortierung=1)
        s.add(kategorie)
        s.commit()
        s.refresh(kategorie)

        pizza = Artikel(
            kategorie_id=kategorie.id,
            name="Margherita",
            preis=Decimal("15.00"),
            verfuegbar=True,
        )
        s.add(pizza)

        salami = Zutat(name="Salami", preis_pro_einheit=Decimal("2.50"))
        pilze = Zutat(name="Pilze", preis_pro_einheit=Decimal("1.50"))
        s.add(salami)
        s.add(pilze)

        s.commit()
        s.refresh(adresse)
        s.refresh(pizza)
        s.refresh(salami)
        s.refresh(pilze)

        # IDs zurückgeben — nach Session-Close sind Objekte detached
        ids = {
            "kunde_id": kunde.id,
            "adresse_id": adresse.id,
            "pizza_id": pizza.id,
            "salami_id": salami.id,
            "pilze_id": pilze.id,
        }

    # Wichtig: Warenkorb-Klassen-State zwischen Tests leeren, sonst
    # bleibt der Korb von Test zu Test bestehen!
    BestellService._waren_koerbe.clear()
    return ids


# ---------------------------------------------------------------------------
# Warenkorb — Basisfälle
# ---------------------------------------------------------------------------


def test_leerer_warenkorb_initial(basis_daten):
    """Ein Kunde, der noch nichts in den Korb gelegt hat, hat einen
    leeren Korb mit Summe 0."""
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert inhalt.items == []
    assert inhalt.gesamtsumme == Decimal("0.00")
    assert not inhalt.mindestbestellwert_erreicht


def test_artikel_hinzufuegen_und_summe(basis_daten):
    """Artikel hinzufügen erhöht die Summe korrekt."""
    BestellService.artikel_hinzufuegen(
        kunden_id=basis_daten["kunde_id"],
        artikel_id=basis_daten["pizza_id"],
        menge=2,
    )
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert len(inhalt.items) == 1
    assert inhalt.items[0].menge == 2
    # 2 × 15.00 = 30.00
    assert inhalt.gesamtsumme == Decimal("30.00")
    assert inhalt.mindestbestellwert_erreicht  # 30 >= 20


def test_zweimal_gleicher_artikel_mergt_menge(basis_daten):
    """Wenn derselbe Artikel zweimal hinzugefügt wird, summiert sich die
    Menge — wir wollen kein Doppel-Item im Korb."""
    BestellService.artikel_hinzufuegen(
        basis_daten["kunde_id"], basis_daten["pizza_id"], 1
    )
    BestellService.artikel_hinzufuegen(
        basis_daten["kunde_id"], basis_daten["pizza_id"], 2
    )
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert len(inhalt.items) == 1
    assert inhalt.items[0].menge == 3


def test_artikel_existiert_nicht_wirft_value_error(basis_daten):
    """Nicht existierender Artikel -> ValueError mit klarer Botschaft."""
    with pytest.raises(ValueError, match="existiert nicht"):
        BestellService.artikel_hinzufuegen(
            basis_daten["kunde_id"], artikel_id=99999, menge=1
        )


# ---------------------------------------------------------------------------
# Wunschpizza
# ---------------------------------------------------------------------------


def test_wunschpizza_preis_inkl_zutaten(basis_daten):
    """Eine Wunschpizza Margherita + Salami + Pilze kostet
    15.00 + 2.50 + 1.50 = 19.00."""
    BestellService.wunschpizza_hinzufuegen(
        kunden_id=basis_daten["kunde_id"],
        basis_artikel_id=basis_daten["pizza_id"],
        zutat_ids=[basis_daten["salami_id"], basis_daten["pilze_id"]],
        menge=1,
    )
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert len(inhalt.items) == 1
    item = inhalt.items[0]
    assert item.ist_wunschpizza
    assert item.zutaten_preis_pro_pizza() == Decimal("4.00")
    assert item.positionssumme() == Decimal("19.00")
    assert inhalt.gesamtsumme == Decimal("19.00")


def test_zwei_wunschpizzas_bleiben_separate_items(basis_daten):
    """Zwei Wunschpizzas mit gleicher Basis werden NICHT gemergt — auch
    wenn die Zutaten gleich wären."""
    BestellService.wunschpizza_hinzufuegen(
        basis_daten["kunde_id"],
        basis_daten["pizza_id"],
        [basis_daten["salami_id"]],
    )
    BestellService.wunschpizza_hinzufuegen(
        basis_daten["kunde_id"],
        basis_daten["pizza_id"],
        [basis_daten["pilze_id"]],
    )
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert len(inhalt.items) == 2


# ---------------------------------------------------------------------------
# Menge ändern / entfernen
# ---------------------------------------------------------------------------


def test_menge_aendern_setzt_neue_menge(basis_daten):
    item = BestellService.artikel_hinzufuegen(
        basis_daten["kunde_id"], basis_daten["pizza_id"], 1
    )
    BestellService.menge_aendern(
        basis_daten["kunde_id"], item.temp_id, neue_menge=5
    )
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert inhalt.items[0].menge == 5


def test_menge_null_entfernt_item(basis_daten):
    """Menge auf 0 setzen = Item entfernen (nutzerfreundlich)."""
    item = BestellService.artikel_hinzufuegen(
        basis_daten["kunde_id"], basis_daten["pizza_id"], 3
    )
    BestellService.menge_aendern(
        basis_daten["kunde_id"], item.temp_id, neue_menge=0
    )
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert inhalt.items == []


# ---------------------------------------------------------------------------
# Mindestbestellwert
# ---------------------------------------------------------------------------


def test_mindestbestellwert_blockiert_bestellung(basis_daten):
    """Bestellung unter 20 CHF -> ValueError."""
    # Nur 1 Pizza = 15 CHF, unter dem Mindestbestellwert von 20
    BestellService.artikel_hinzufuegen(
        basis_daten["kunde_id"], basis_daten["pizza_id"], 1
    )
    with pytest.raises(ValueError, match="Mindestbestellwert"):
        BestellService.bestellung_aufgeben(
            kunden_id=basis_daten["kunde_id"],
            lieferadresse_id=basis_daten["adresse_id"],
        )


def test_leerer_warenkorb_kann_nicht_bestellt_werden(basis_daten):
    with pytest.raises(ValueError, match="leer"):
        BestellService.bestellung_aufgeben(
            kunden_id=basis_daten["kunde_id"],
            lieferadresse_id=basis_daten["adresse_id"],
        )


# ---------------------------------------------------------------------------
# Erfolgreicher Bestell-Flow (end-to-end)
# ---------------------------------------------------------------------------


def test_bestellung_aufgeben_erfolgreich(basis_daten, tmp_db):
    """Happy Path: Warenkorb füllen, bestellen, in der DB nachschauen."""
    BestellService.artikel_hinzufuegen(
        basis_daten["kunde_id"], basis_daten["pizza_id"], menge=2
    )
    BestellService.wunschpizza_hinzufuegen(
        basis_daten["kunde_id"],
        basis_daten["pizza_id"],
        [basis_daten["salami_id"]],
    )

    ergebnis = BestellService.bestellung_aufgeben(
        kunden_id=basis_daten["kunde_id"],
        lieferadresse_id=basis_daten["adresse_id"],
        zahlungsmethode="karte",
    )

    # 2× Margherita = 30.00, 1× Wunschpizza (Margherita + Salami) = 17.50
    assert ergebnis.gesamtbetrag == Decimal("47.50")
    assert ergebnis.bestellung_id > 0

    # Warenkorb sollte nach der Bestellung leer sein
    inhalt = BestellService.warenkorb_lesen(basis_daten["kunde_id"])
    assert inhalt.items == []

    # In der DB nachschauen: Bestellung mit Status OFFEN + bezahlte Zahlung
    from domain.models import Bestellung, Zahlung
    with Session(tmp_db) as s:
        bestellung = s.get(Bestellung, ergebnis.bestellung_id)
        assert bestellung is not None
        assert bestellung.status == BestellStatus.OFFEN
        assert bestellung.gesamtbetrag == Decimal("47.50")

        # Zahlung muss BEZAHLT sein (Fake-Service ist immer erfolgreich)
        from sqlmodel import select
        zahlung = s.exec(
            select(Zahlung).where(Zahlung.bestellung_id == bestellung.id)
        ).first()
        assert zahlung is not None
        assert zahlung.status == ZahlungStatus.BEZAHLT
        assert zahlung.transaktions_id is not None
        assert zahlung.transaktions_id.startswith("FAKE-")
