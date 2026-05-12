"""
Tests — ArtikelService
=======================
Tests für die Business-Logik des `ArtikelService`.

Fokus liegt hier auf den Dingen, die im Service drin sind und die
DAOs nicht abdecken:
  - Soft-Check beim Anlegen/Bearbeiten von Artikeln (Duplikat „Name +
    Kategorie") liefert eine Warnung, ABER speichert trotzdem.
  - „Nicht gefunden" wirft `ValueError` mit lesbarer Botschaft.
  - `rezept_setzen` ist atomar — wenn die Validierung scheitert, bleibt
    das alte Rezept unangetastet.
  - Aggregation: `menue_laden` gruppiert korrekt nach Kategorie und
    respektiert die Filter-Flags.
  - Unique-Constraints (Kategorie, Zutat) werden vom Service vorab
    geprüft, statt eine rohe IntegrityError durchzureichen.

Wir verwenden das `db_engine`-Fixture aus conftest, das `utils.db.engine`
patcht — damit nutzt `get_session()` im Service automatisch die
In-Memory-Test-DB.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from dao.artikel_zutat_dao import ArtikelZutatDAO
from services.artikel_service import (
    ArtikelMitWarnung,
    ArtikelService,
    MenueEintrag,
)
from utils.db import get_session


# ===========================================================================
# menue_laden
# ===========================================================================


class TestMenueLaden:
    """Aggregation Kategorie + Artikel."""

    def test_leeres_menue(self, db_engine):
        """Frische DB ohne Daten -> leere Liste."""
        assert ArtikelService.menue_laden() == []

    def test_gruppiert_nach_kategorie(
        self, db_engine, kategorie_pizzen, artikel_margherita
    ):
        menue = ArtikelService.menue_laden()
        assert len(menue) == 1
        eintrag = menue[0]
        assert isinstance(eintrag, MenueEintrag)
        assert eintrag.kategorie.name == "Pizzen"
        assert [a.name for a in eintrag.artikel] == ["Margherita"]

    def test_filter_nur_verfuegbar(
        self, db_engine, kategorie_pizzen, artikel_margherita
    ):
        # Margherita ausverkauft setzen.
        ArtikelService.verfuegbarkeit_umschalten(artikel_margherita.id)
        # Default: nur verfügbare Artikel -> Margherita raus, Kategorie wird
        # damit auch ausgeblendet (leere_kategorien_zeigen=False).
        menue = ArtikelService.menue_laden(nur_verfuegbar=True)
        assert menue == []
        # Mit Admin-Sicht: alle Artikel inkl. ausverkauft.
        menue_admin = ArtikelService.menue_laden(
            nur_verfuegbar=False, leere_kategorien_zeigen=True
        )
        assert len(menue_admin) == 1

    def test_leere_kategorien_optional_zeigen(
        self, db_engine, kategorie_pizzen, kategorie_getraenke, artikel_margherita
    ):
        """Getränke hat keinen Artikel -> default ausgeblendet, opt-in einblendbar."""
        nur_volle = ArtikelService.menue_laden(leere_kategorien_zeigen=False)
        alle = ArtikelService.menue_laden(leere_kategorien_zeigen=True)
        assert {e.kategorie.name for e in nur_volle} == {"Pizzen"}
        assert {e.kategorie.name for e in alle} == {"Pizzen", "Getränke"}


# ===========================================================================
# artikel_anlegen — inkl. Soft-Check
# ===========================================================================


class TestArtikelAnlegen:
    """Soft-Check auf Name+Kategorie + Validierungen."""

    def test_happy_path_keine_warnung(self, db_engine, kategorie_pizzen):
        ergebnis = ArtikelService.artikel_anlegen(
            name="Quattro Stagioni",
            kategorie_id=kategorie_pizzen.id,
            preis=Decimal("17.50"),
        )
        assert isinstance(ergebnis, ArtikelMitWarnung)
        assert ergebnis.artikel.id is not None
        assert ergebnis.warnungen == []

    def test_unbekannte_kategorie_wirft_value_error(self, db_engine):
        with pytest.raises(ValueError, match="Kategorie"):
            ArtikelService.artikel_anlegen(
                name="Test", kategorie_id=9999, preis=Decimal("10.00")
            )

    def test_duplikat_name_in_gleicher_kategorie_warnt(
        self, db_engine, kategorie_pizzen, artikel_margherita
    ):
        """Same Name + same Kategorie -> Speichern OK, aber Warnung."""
        ergebnis = ArtikelService.artikel_anlegen(
            name="Margherita",
            kategorie_id=kategorie_pizzen.id,
            preis=Decimal("18.00"),
        )
        # Wichtig: trotzdem gespeichert (Soft-Check, kein Hard-Block).
        assert ergebnis.artikel.id is not None
        assert ergebnis.artikel.id != artikel_margherita.id
        assert len(ergebnis.warnungen) == 1
        assert "bereits" in ergebnis.warnungen[0]

    def test_duplikat_name_case_insensitive(
        self, db_engine, kategorie_pizzen, artikel_margherita
    ):
        ergebnis = ArtikelService.artikel_anlegen(
            name="MARGHERITA",
            kategorie_id=kategorie_pizzen.id,
            preis=Decimal("18.00"),
        )
        assert len(ergebnis.warnungen) == 1

    def test_gleicher_name_in_anderer_kategorie_keine_warnung(
        self,
        db_engine,
        kategorie_pizzen,
        kategorie_getraenke,
        artikel_margherita,
    ):
        """„Margherita" als Pizza und „Margherita" als Cocktail -> ok."""
        ergebnis = ArtikelService.artikel_anlegen(
            name="Margherita",
            kategorie_id=kategorie_getraenke.id,
            preis=Decimal("9.00"),
        )
        assert ergebnis.warnungen == []


# ===========================================================================
# artikel_bearbeiten
# ===========================================================================


class TestArtikelBearbeiten:
    """Teil-Updates und Soft-Check beim Umbenennen."""

    def test_partial_update_aendert_nur_uebergebene_felder(
        self, db_engine, artikel_margherita
    ):
        ergebnis = ArtikelService.artikel_bearbeiten(
            artikel_margherita.id, preis=Decimal("16.00")
        )
        assert ergebnis.artikel.preis == Decimal("16.00")
        # Name unverändert.
        assert ergebnis.artikel.name == "Margherita"

    def test_unbekannter_artikel_wirft_value_error(self, db_engine):
        with pytest.raises(ValueError, match="Artikel"):
            ArtikelService.artikel_bearbeiten(9999, name="X")

    def test_umbenennen_auf_eigenen_namen_warnt_nicht(
        self, db_engine, artikel_margherita
    ):
        """Wenn man den Artikel selbst editiert ohne Namen zu ändern,
        soll der Soft-Check ihn NICHT als Duplikat behandeln."""
        ergebnis = ArtikelService.artikel_bearbeiten(
            artikel_margherita.id, name="Margherita", preis=Decimal("15.00")
        )
        assert ergebnis.warnungen == []

    def test_umbenennen_auf_existierenden_warnt(
        self, db_engine, kategorie_pizzen, artikel_margherita
    ):
        # Eine zweite Pizza, die wir später überschneidend umbenennen.
        zweite = ArtikelService.artikel_anlegen(
            name="Salami",
            kategorie_id=kategorie_pizzen.id,
            preis=Decimal("16.00"),
        )
        ergebnis = ArtikelService.artikel_bearbeiten(
            zweite.artikel.id, name="Margherita"
        )
        assert len(ergebnis.warnungen) == 1


# ===========================================================================
# verfuegbarkeit_umschalten + artikel_loeschen
# ===========================================================================


class TestVerfuegbarkeitUndLoeschen:
    def test_verfuegbarkeit_toggelt(self, db_engine, artikel_margherita):
        # Default true -> nach toggle false.
        nach_erstem = ArtikelService.verfuegbarkeit_umschalten(
            artikel_margherita.id
        )
        assert nach_erstem.verfuegbar is False
        # Zweimal -> wieder true.
        nach_zweitem = ArtikelService.verfuegbarkeit_umschalten(
            artikel_margherita.id
        )
        assert nach_zweitem.verfuegbar is True

    def test_verfuegbarkeit_unbekannte_id(self, db_engine):
        with pytest.raises(ValueError):
            ArtikelService.verfuegbarkeit_umschalten(9999)

    def test_artikel_loeschen(self, db_engine, artikel_margherita):
        assert ArtikelService.artikel_loeschen(artikel_margherita.id) is True
        assert ArtikelService.artikel_loeschen(artikel_margherita.id) is False


# ===========================================================================
# rezept_setzen — atomar
# ===========================================================================


class TestRezeptSetzen:
    """Atomares Ersetzen des Standard-Rezepts."""

    def test_rezept_neu_aufbauen(
        self,
        db_engine,
        artikel_margherita,
        zutat_mozzarella,
        zutat_salami,
    ):
        ergebnis = ArtikelService.rezept_setzen(
            artikel_margherita.id,
            [
                (zutat_mozzarella.id, Decimal("1")),
                (zutat_salami.id, Decimal("0.5")),
            ],
        )
        assert len(ergebnis) == 2
        # Eager-loaded Zutat ist verfügbar (für die UI wichtig).
        namen = {e.zutat.name for e in ergebnis}
        assert namen == {"Mozzarella", "Salami"}

    def test_rezept_ersetzen_loescht_altes(
        self,
        db_engine,
        artikel_margherita,
        zutat_mozzarella,
        zutat_salami,
    ):
        # Erst nur Mozzarella.
        ArtikelService.rezept_setzen(
            artikel_margherita.id, [(zutat_mozzarella.id, Decimal("1"))]
        )
        # Jetzt auf Salami umstellen — Mozzarella muss raus.
        ArtikelService.rezept_setzen(
            artikel_margherita.id, [(zutat_salami.id, Decimal("1"))]
        )
        with get_session() as session:
            rezept = ArtikelZutatDAO.rezept_laden(
                session, artikel_margherita.id
            )
        assert {e.zutat_id for e in rezept} == {zutat_salami.id}

    def test_leeres_rezept_loescht_alles(
        self, db_engine, artikel_margherita, zutat_mozzarella
    ):
        ArtikelService.rezept_setzen(
            artikel_margherita.id, [(zutat_mozzarella.id, Decimal("1"))]
        )
        ArtikelService.rezept_setzen(artikel_margherita.id, [])
        with get_session() as session:
            assert (
                ArtikelZutatDAO.rezept_laden(session, artikel_margherita.id)
                == []
            )

    def test_unbekannte_zutat_rollt_zurueck(
        self, db_engine, artikel_margherita, zutat_mozzarella
    ):
        """Wenn eine Zutat-ID ungültig ist, soll NICHTS geändert werden —
        weder das alte Rezept gelöscht noch ein Teil eingefügt."""
        # Ausgangs-Rezept etablieren.
        ArtikelService.rezept_setzen(
            artikel_margherita.id, [(zutat_mozzarella.id, Decimal("1"))]
        )
        # Versuch: Mozzarella + ungültige ID.
        with pytest.raises(ValueError, match="Zutat"):
            ArtikelService.rezept_setzen(
                artikel_margherita.id,
                [
                    (zutat_mozzarella.id, Decimal("2")),
                    (9999, Decimal("1")),
                ],
            )
        # Altes Rezept muss noch da sein, unverändert.
        with get_session() as session:
            rezept = ArtikelZutatDAO.rezept_laden(
                session, artikel_margherita.id
            )
        assert len(rezept) == 1
        assert rezept[0].zutat_id == zutat_mozzarella.id
        # Die Menge ist die ursprüngliche, nicht die „2" aus dem fehlgeschlagenen Versuch.
        assert rezept[0].menge == Decimal("1")

    def test_unbekannter_artikel_wirft(self, db_engine, zutat_mozzarella):
        with pytest.raises(ValueError, match="Artikel"):
            ArtikelService.rezept_setzen(
                9999, [(zutat_mozzarella.id, Decimal("1"))]
            )


# ===========================================================================
# Kategorien — CRUD via Service
# ===========================================================================


class TestKategorieService:
    def test_anlegen_und_alle(self, db_engine):
        ArtikelService.kategorie_anlegen(name="Pasta", sortierung=2)
        ArtikelService.kategorie_anlegen(name="Pizza", sortierung=1)
        alle = ArtikelService.kategorien_alle()
        # Sortierung steuert die Reihenfolge — Pizza (sortierung=1) zuerst.
        assert [k.name for k in alle] == ["Pizza", "Pasta"]

    def test_anlegen_duplikat_wirft(self, db_engine, kategorie_pizzen):
        with pytest.raises(ValueError, match="bereits"):
            ArtikelService.kategorie_anlegen(name="Pizzen")

    def test_bearbeiten_eigenen_namen_kein_fehler(
        self, db_engine, kategorie_pizzen
    ):
        ergebnis = ArtikelService.kategorie_bearbeiten(
            kategorie_pizzen.id, name="Pizzen", beschreibung="Neu"
        )
        assert ergebnis.beschreibung == "Neu"

    def test_bearbeiten_auf_existierenden_namen_wirft(
        self, db_engine, kategorie_pizzen, kategorie_getraenke
    ):
        with pytest.raises(ValueError, match="bereits"):
            ArtikelService.kategorie_bearbeiten(
                kategorie_getraenke.id, name="Pizzen"
            )

    def test_loeschen_leere_kategorie(self, db_engine, kategorie_getraenke):
        assert (
            ArtikelService.kategorie_loeschen(kategorie_getraenke.id) is True
        )


# ===========================================================================
# Zutaten — CRUD via Service
# ===========================================================================


class TestZutatService:
    def test_anlegen_und_alle(self, db_engine):
        ArtikelService.zutat_anlegen(
            name="Pilze", preis_pro_einheit=Decimal("1.50")
        )
        alle = ArtikelService.zutaten_alle()
        assert [z.name for z in alle] == ["Pilze"]

    def test_anlegen_duplikat_wirft(self, db_engine, zutat_mozzarella):
        with pytest.raises(ValueError, match="bereits"):
            ArtikelService.zutat_anlegen(
                name="Mozzarella", preis_pro_einheit=Decimal("3.00")
            )

    def test_verfuegbarkeit_toggelt(self, db_engine, zutat_mozzarella):
        nach_erstem = ArtikelService.zutat_verfuegbarkeit_umschalten(
            zutat_mozzarella.id
        )
        assert nach_erstem.verfuegbar is False
        nach_zweitem = ArtikelService.zutat_verfuegbarkeit_umschalten(
            zutat_mozzarella.id
        )
        assert nach_zweitem.verfuegbar is True

    def test_filter_kombination(
        self, db_engine, zutat_mozzarella, zutat_salami
    ):
        # Beide vegetarisch + verfügbar -> nur Mozzarella.
        nur_veg_verfuegbar = ArtikelService.zutaten_alle(
            nur_vegetarisch=True, nur_verfuegbar=True
        )
        assert {z.name for z in nur_veg_verfuegbar} == {"Mozzarella"}

    def test_bearbeiten_unbekannte_id_wirft(self, db_engine):
        with pytest.raises(ValueError, match="Zutat"):
            ArtikelService.zutat_bearbeiten(9999, name="X")
