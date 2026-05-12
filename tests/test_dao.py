"""
Tests — DAOs
=============
Smoke-Tests für `KategorieDAO`, `ZutatDAO`, `ArtikelDAO`,
`ArtikelZutatDAO`.

Fokus:
  - CRUD-Roundtrips (anlegen → lesen → ändern → löschen).
  - Spezifische Queries (Filter-Flags, Sortierung, Suche).
  - FK-Verhalten: Verbotenes Löschen wirft IntegrityError, weil wir in
    der Test-Engine `PRAGMA foreign_keys=ON` haben (wie produktiv).

Was wir bewusst NICHT testen:
  - Triviale Pass-Through-Methoden (z. B. `session.get`) — das wäre
    SQLAlchemy-Test, kein Code-von-uns-Test.
  - Performance, Race-Conditions — Studienprojekt-Scope.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from dao.artikel_dao import ArtikelDAO
from dao.artikel_zutat_dao import ArtikelZutatDAO
from dao.kategorie_dao import KategorieDAO
from dao.zutat_dao import ZutatDAO
from domain.models import Artikel, Kategorie, Zutat


# ===========================================================================
# KategorieDAO
# ===========================================================================


class TestKategorieDAO:
    """CRUD und Sortierung für Kategorien."""

    def test_create_setzt_id(self, db_session):
        """Nach `create` muss die Primary-Key-ID am Objekt stehen."""
        kategorie = Kategorie(name="Pasta", sortierung=3)
        gespeichert = KategorieDAO.create(db_session, kategorie)
        assert gespeichert.id is not None
        # Identität: der Service hat das gleiche Objekt zurück, nicht eine Kopie.
        assert gespeichert is kategorie

    def test_get_by_id_und_by_name(self, db_session, kategorie_pizzen):
        gefunden_per_id = KategorieDAO.get_by_id(db_session, kategorie_pizzen.id)
        gefunden_per_name = KategorieDAO.get_by_name(db_session, "Pizzen")
        assert gefunden_per_id is not None
        assert gefunden_per_name is not None
        assert gefunden_per_id.id == kategorie_pizzen.id
        assert gefunden_per_name.id == kategorie_pizzen.id

    def test_get_by_id_nicht_existent_gibt_none(self, db_session):
        assert KategorieDAO.get_by_id(db_session, 9999) is None

    def test_get_all_sortiert_nach_sortierung(
        self, db_session, kategorie_pizzen, kategorie_getraenke
    ):
        # Pizzen hat sortierung=1, Getränke sortierung=2 -> Pizzen zuerst.
        alle = KategorieDAO.get_all(db_session, sortiert=True)
        assert [k.name for k in alle] == ["Pizzen", "Getränke"]

    def test_exists(self, db_session, kategorie_pizzen):
        assert KategorieDAO.exists(db_session, "Pizzen") is True
        assert KategorieDAO.exists(db_session, "Sushi") is False

    def test_update_aendert_felder(self, db_session, kategorie_pizzen):
        kategorie_pizzen.beschreibung = "Hausgemacht"
        aktualisiert = KategorieDAO.update(db_session, kategorie_pizzen)
        assert aktualisiert.beschreibung == "Hausgemacht"
        # Frisch laden zum Beweis, dass es persistiert wurde.
        frisch = KategorieDAO.get_by_id(db_session, kategorie_pizzen.id)
        assert frisch.beschreibung == "Hausgemacht"

    def test_delete_loescht_und_gibt_true(self, db_session, kategorie_getraenke):
        # Getränke hat keine Artikel -> sollte ohne FK-Probleme gehen.
        assert KategorieDAO.delete(db_session, kategorie_getraenke.id) is True
        assert KategorieDAO.get_by_id(db_session, kategorie_getraenke.id) is None

    def test_delete_nicht_existent_gibt_false(self, db_session):
        assert KategorieDAO.delete(db_session, 9999) is False

    def test_delete_mit_artikeln_wirft_integrity_error(
        self, db_session, kategorie_pizzen, artikel_margherita
    ):
        """FK-Schutz: Kategorie mit Artikeln darf nicht gelöscht werden."""
        with pytest.raises(IntegrityError):
            KategorieDAO.delete(db_session, kategorie_pizzen.id)
            db_session.commit()  # hier knallt's bei FK-aktiviertem SQLite


# ===========================================================================
# ZutatDAO
# ===========================================================================


class TestZutatDAO:
    """CRUD plus Filter-Flags."""

    def test_create_und_get(self, db_session):
        zutat = Zutat(
            name="Pilze", preis_pro_einheit=Decimal("1.50"), vegetarisch=True
        )
        gespeichert = ZutatDAO.create(db_session, zutat)
        assert gespeichert.id is not None

        # Per Name auffindbar (unique-Feld).
        per_name = ZutatDAO.get_by_name(db_session, "Pilze")
        assert per_name is not None
        assert per_name.id == gespeichert.id

    def test_get_all_filter_nur_verfuegbar(
        self, db_session, zutat_mozzarella, zutat_salami
    ):
        # Salami auf nicht-verfügbar setzen -> nur Mozzarella sollte kommen.
        ZutatDAO.verfuegbarkeit_setzen(db_session, zutat_salami.id, False)
        verfuegbar = ZutatDAO.get_all(db_session, nur_verfuegbar=True)
        assert {z.name for z in verfuegbar} == {"Mozzarella"}

    def test_get_all_filter_nur_vegetarisch(
        self, db_session, zutat_mozzarella, zutat_salami
    ):
        veggie = ZutatDAO.get_all(db_session, nur_vegetarisch=True)
        assert {z.name for z in veggie} == {"Mozzarella"}

    def test_get_all_filter_kombiniert(
        self, db_session, zutat_mozzarella, zutat_salami
    ):
        # Beide Flags wirken kumulativ: vegetarisch UND verfügbar.
        kombiniert = ZutatDAO.get_all(
            db_session, nur_vegetarisch=True, nur_verfuegbar=True
        )
        assert {z.name for z in kombiniert} == {"Mozzarella"}

    def test_verfuegbarkeit_setzen_idempotent(self, db_session, zutat_mozzarella):
        # Zweimal auf False setzen -> bleibt False, kein Fehler.
        ZutatDAO.verfuegbarkeit_setzen(db_session, zutat_mozzarella.id, False)
        ZutatDAO.verfuegbarkeit_setzen(db_session, zutat_mozzarella.id, False)
        frisch = ZutatDAO.get_by_id(db_session, zutat_mozzarella.id)
        assert frisch.verfuegbar is False

    def test_verfuegbarkeit_setzen_unbekannte_id(self, db_session):
        assert ZutatDAO.verfuegbarkeit_setzen(db_session, 9999, True) is None

    def test_unique_name_constraint(self, db_session, zutat_mozzarella):
        """Zwei Zutaten mit gleichem Namen sind im Modell verboten."""
        duplikat = Zutat(name="Mozzarella", preis_pro_einheit=Decimal("1.00"))
        with pytest.raises(IntegrityError):
            ZutatDAO.create(db_session, duplikat)
            db_session.commit()


# ===========================================================================
# ArtikelDAO
# ===========================================================================


class TestArtikelDAO:
    """Artikel-CRUD plus Kategorie-Filter und Suche."""

    def test_create_und_get_nach_kategorie(
        self, db_session, kategorie_pizzen
    ):
        artikel = Artikel(
            name="Salami",
            kategorie_id=kategorie_pizzen.id,
            preis=Decimal("16.00"),
        )
        ArtikelDAO.create(db_session, artikel)
        liste = ArtikelDAO.get_nach_kategorie(db_session, kategorie_pizzen.id)
        assert [a.name for a in liste] == ["Salami"]

    def test_get_nach_kategorie_filter_verfuegbar(
        self, db_session, kategorie_pizzen, artikel_margherita
    ):
        # Margherita auf nicht-verfügbar setzen.
        ArtikelDAO.verfuegbarkeit_setzen(
            db_session, artikel_margherita.id, False
        )
        nur_aktive = ArtikelDAO.get_nach_kategorie(
            db_session, kategorie_pizzen.id, nur_verfuegbar=True
        )
        alle = ArtikelDAO.get_nach_kategorie(
            db_session, kategorie_pizzen.id, nur_verfuegbar=False
        )
        assert nur_aktive == []
        assert len(alle) == 1

    def test_suchen_nach_name_case_insensitive(
        self, db_session, kategorie_pizzen, artikel_margherita
    ):
        """ilike-Substring-Suche muss case-insensitive matchen."""
        treffer = ArtikelDAO.suchen_nach_name(db_session, "marg")
        assert len(treffer) == 1
        assert treffer[0].name == "Margherita"

    def test_suchen_nach_name_kein_treffer(self, db_session, artikel_margherita):
        assert ArtikelDAO.suchen_nach_name(db_session, "Sushi") == []

    def test_delete_artikel_ohne_referenzen(self, db_session, artikel_margherita):
        assert ArtikelDAO.delete(db_session, artikel_margherita.id) is True
        assert ArtikelDAO.get_by_id(db_session, artikel_margherita.id) is None


# ===========================================================================
# ArtikelZutatDAO (Junction)
# ===========================================================================


class TestArtikelZutatDAO:
    """Junction-Tabelle: Hinzufügen, Aktualisieren, Eager-Load, Bulk-Löschen."""

    def test_zutat_hinzufuegen_und_rezept_laden(
        self,
        db_session,
        artikel_margherita,
        zutat_mozzarella,
        zutat_salami,
    ):
        ArtikelZutatDAO.zutat_hinzufuegen(
            db_session,
            artikel_margherita.id,
            zutat_mozzarella.id,
            menge=Decimal("1"),
        )
        ArtikelZutatDAO.zutat_hinzufuegen(
            db_session,
            artikel_margherita.id,
            zutat_salami.id,
            menge=Decimal("0.5"),
        )
        rezept = ArtikelZutatDAO.rezept_laden(db_session, artikel_margherita.id)
        assert len(rezept) == 2
        # Eager-Loading prüfen: .zutat ist befüllt, kein Lazy-Trigger.
        for eintrag in rezept:
            assert eintrag.zutat is not None

    def test_zutat_hinzufuegen_duplikat_wirft(
        self, db_session, artikel_margherita, zutat_mozzarella
    ):
        """Composite Primary Key verhindert dieselbe Zutat zweimal."""
        ArtikelZutatDAO.zutat_hinzufuegen(
            db_session, artikel_margherita.id, zutat_mozzarella.id
        )
        with pytest.raises(IntegrityError):
            ArtikelZutatDAO.zutat_hinzufuegen(
                db_session, artikel_margherita.id, zutat_mozzarella.id
            )
            db_session.commit()

    def test_menge_aktualisieren(
        self, db_session, artikel_margherita, zutat_mozzarella
    ):
        ArtikelZutatDAO.zutat_hinzufuegen(
            db_session, artikel_margherita.id, zutat_mozzarella.id
        )
        aktualisiert = ArtikelZutatDAO.menge_aktualisieren(
            db_session,
            artikel_margherita.id,
            zutat_mozzarella.id,
            Decimal("2.0"),
        )
        assert aktualisiert is not None
        assert aktualisiert.menge == Decimal("2.0")

    def test_menge_aktualisieren_unbekannte_kombi(
        self, db_session, artikel_margherita, zutat_mozzarella
    ):
        # Existiert nicht -> None.
        ergebnis = ArtikelZutatDAO.menge_aktualisieren(
            db_session,
            artikel_margherita.id,
            zutat_mozzarella.id,
            Decimal("3.0"),
        )
        assert ergebnis is None

    def test_zutat_entfernen_idempotent(
        self, db_session, artikel_margherita, zutat_mozzarella
    ):
        ArtikelZutatDAO.zutat_hinzufuegen(
            db_session, artikel_margherita.id, zutat_mozzarella.id
        )
        # Erstmal: löschen geht.
        assert (
            ArtikelZutatDAO.zutat_entfernen(
                db_session, artikel_margherita.id, zutat_mozzarella.id
            )
            is True
        )
        # Zweiter Aufruf: nichts mehr da, aber kein Fehler.
        assert (
            ArtikelZutatDAO.zutat_entfernen(
                db_session, artikel_margherita.id, zutat_mozzarella.id
            )
            is False
        )

    def test_rezept_loeschen_bulk(
        self,
        db_session,
        artikel_margherita,
        zutat_mozzarella,
        zutat_salami,
    ):
        ArtikelZutatDAO.zutat_hinzufuegen(
            db_session, artikel_margherita.id, zutat_mozzarella.id
        )
        ArtikelZutatDAO.zutat_hinzufuegen(
            db_session, artikel_margherita.id, zutat_salami.id
        )
        anzahl = ArtikelZutatDAO.rezept_loeschen(
            db_session, artikel_margherita.id
        )
        assert anzahl == 2
        # Liste ist jetzt leer.
        assert (
            ArtikelZutatDAO.rezept_laden(db_session, artikel_margherita.id) == []
        )
