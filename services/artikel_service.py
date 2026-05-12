"""
Service — Artikel
==================
Business-Logik rund um Menü, Artikel und Standard-Rezepte.

Dieser Service ist die Facade vor den vier Menü-DAOs (`ArtikelDAO`,
`KategorieDAO`, `ZutatDAO`, `ArtikelZutatDAO`). Er ist der einzige
Einstiegspunkt für die Pages — keine Page ruft direkt eine DAO auf.

Verantwortlichkeiten:
  - Menü-Aggregation (Kategorien zusammen mit ihren Artikeln) für die
    Kunden- und Admin-UI.
  - CRUD für Artikel, mit Soft-Validierung (warnt z. B. bei einem
    möglichen Duplikat „Name + Kategorie" — siehe `artikel_anlegen`).
  - CRUD für Kategorien und Zutaten (vom Admin-Bereich genutzt). Beide
    haben ein Unique-Feld `name` — daher hier harte Duplikat-Prüfung
    statt Soft-Check (sonst würde der DB-Constraint scheitern).
  - Verwaltung der Standard-Rezepte (welche Zutaten in welcher Menge).
  - Transaktions-Grenze: Jede Service-Methode öffnet ihre eigene
    `get_session()`. Mehrere DAO-Aufrufe innerhalb einer Methode laufen
    damit in einer Transaktion (Commit am Ende, Rollback bei Exception).

Designentscheidungen:
  - Soft-Check beim Anlegen: Im Modell ist `Artikel.name` NICHT unique
    (gewollt, weil z. B. „Pizza Margherita" in verschiedenen Grössen
    existieren kann). Wir warnen aber, wenn in derselben Kategorie
    schon ein Artikel mit gleichem Namen liegt — die Page entscheidet
    dann, ob sie eine Bestätigung vom Admin holt oder einfach speichert.
  - Rückgabewerte mit Daten + Warnungen sind kleine Dataclasses
    (`ArtikelMitWarnung`, `MenueEintrag`). Klarer als nackte Tupel und
    von der Page direkt benutzbar.
  - „Nicht gefunden" wirft `ValueError` mit klarer Botschaft. Die
    Page fängt das und zeigt eine UI-Meldung.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from dao.artikel_dao import ArtikelDAO
from dao.artikel_zutat_dao import ArtikelZutatDAO
from dao.kategorie_dao import KategorieDAO
from dao.zutat_dao import ZutatDAO
from domain.models import Artikel, ArtikelZutat, Kategorie, Zutat
from utils.db import get_session


# ---------------------------------------------------------------------------
# Rückgabe-Typen
# ---------------------------------------------------------------------------


@dataclass
class MenueEintrag:
    """Eine Kategorie zusammen mit ihren Artikeln.

    Wird von `menue_laden()` als Element einer Liste zurückgegeben.
    Die Page kann direkt drüber iterieren:
        for eintrag in menue:
            ui.label(eintrag.kategorie.name)
            for artikel in eintrag.artikel: ...
    """

    kategorie: Kategorie
    artikel: list[Artikel]


@dataclass
class ArtikelMitWarnung:
    """Ergebnis von `artikel_anlegen` / `artikel_bearbeiten`.

    `warnungen` ist eine (oft leere) Liste mit Soft-Hinweisen — z. B.
    ein erkanntes Duplikat. Die Page entscheidet, was damit passiert
    (Toast, Modal, Bestätigung einholen, ignorieren).
    """

    artikel: Artikel
    warnungen: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ArtikelService:
    """Business-Logik für Menü und Artikel-Verwaltung."""

    # =======================================================================
    # Read / Anzeige
    # =======================================================================

    @staticmethod
    def menue_laden(
        *,
        nur_verfuegbar: bool = True,
        leere_kategorien_zeigen: bool = False,
    ) -> list[MenueEintrag]:
        """Lädt das komplette Menü, gruppiert nach Kategorie.

        - `nur_verfuegbar=True` (Default): blendet ausverkaufte Artikel
          aus — passend für die Kunden-Seite. Im Admin-View wird man
          das auf False setzen, um auch ausverkaufte Sachen sehen und
          wieder einschalten zu können.
        - `leere_kategorien_zeigen=False` (Default): Kategorien ohne
          (verfügbare) Artikel werden weggelassen, damit die UI nicht
          mit leeren Sektionen vollläuft.

        Reihenfolge: Kategorien nach `sortierung` + `name`, Artikel
        innerhalb der Kategorie alphabetisch (siehe DAOs).
        """
        with get_session() as session:
            kategorien = KategorieDAO.get_all(session, sortiert=True)
            menue: list[MenueEintrag] = []
            for kategorie in kategorien:
                # mypy/pyright weiss nicht, dass `id` nach get_all gesetzt ist.
                # Im Default-Fall ist die ID nach dem Lesen aus der DB immer da.
                assert kategorie.id is not None
                artikel_liste = ArtikelDAO.get_nach_kategorie(
                    session, kategorie.id, nur_verfuegbar=nur_verfuegbar
                )
                if artikel_liste or leere_kategorien_zeigen:
                    menue.append(MenueEintrag(kategorie=kategorie, artikel=artikel_liste))
            return menue

    @staticmethod
    def artikel_mit_rezept_laden(
        artikel_id: int,
    ) -> tuple[Artikel, list[ArtikelZutat]]:
        """Lädt einen Artikel zusammen mit seinem Standard-Rezept.

        Wirft `ValueError`, wenn der Artikel nicht existiert.
        Das Rezept enthält dank `selectinload` (siehe ArtikelZutatDAO)
        die `Zutat`-Objekte mit — die Page kann also `eintrag.zutat.name`
        lesen, ohne dass die Session noch offen sein muss.
        """
        with get_session() as session:
            artikel = ArtikelDAO.get_by_id(session, artikel_id)
            if artikel is None:
                raise ValueError(f"Artikel mit ID {artikel_id} existiert nicht.")
            rezept = ArtikelZutatDAO.rezept_laden(session, artikel_id)
            return artikel, rezept

    # =======================================================================
    # Artikel — Create / Update / Delete
    # =======================================================================

    @staticmethod
    def artikel_anlegen(
        *,
        name: str,
        kategorie_id: int,
        preis: Decimal,
        beschreibung: Optional[str] = None,
        bild_url: Optional[str] = None,
        verfuegbar: bool = True,
    ) -> ArtikelMitWarnung:
        """Legt einen neuen Artikel an.

        Soft-Check: Wenn in der Ziel-Kategorie schon ein Artikel mit
        identischem Namen (case-insensitive) existiert, wird der Artikel
        trotzdem gespeichert, aber eine Warnung in `ArtikelMitWarnung`
        zurückgegeben. Damit hat die Page die Möglichkeit, dem Admin
        eine Rückfrage zu stellen („Es gibt schon eine Pizza Margherita
        in Pizzen — trotzdem anlegen?").

        Wirft `ValueError`, wenn die `kategorie_id` nicht existiert
        (Vorab-Prüfung statt FK-Constraint-Exception, weil die
        Fehlermeldung damit lesbarer ist).
        """
        with get_session() as session:
            kategorie = KategorieDAO.get_by_id(session, kategorie_id)
            if kategorie is None:
                raise ValueError(
                    f"Kategorie mit ID {kategorie_id} existiert nicht."
                )

            warnungen = ArtikelService._duplikat_pruefen(
                session=session,
                name=name,
                kategorie_id=kategorie_id,
                kategorie_name=kategorie.name,
                ignoriere_artikel_id=None,
            )

            neuer_artikel = Artikel(
                name=name,
                kategorie_id=kategorie_id,
                preis=preis,
                beschreibung=beschreibung,
                bild_url=bild_url,
                verfuegbar=verfuegbar,
            )
            gespeichert = ArtikelDAO.create(session, neuer_artikel)
            return ArtikelMitWarnung(artikel=gespeichert, warnungen=warnungen)

    @staticmethod
    def artikel_bearbeiten(
        artikel_id: int,
        *,
        name: Optional[str] = None,
        kategorie_id: Optional[int] = None,
        preis: Optional[Decimal] = None,
        beschreibung: Optional[str] = None,
        bild_url: Optional[str] = None,
        verfuegbar: Optional[bool] = None,
    ) -> ArtikelMitWarnung:
        """Aktualisiert die übergebenen Felder eines Artikels.

        Konvention: `None` heisst „nicht ändern" — wer ein Optional-Feld
        wie `beschreibung` aktiv leeren will, übergibt einen leeren
        String. Diese Vereinfachung passt für unsere Use-Cases im Admin
        (man editiert dort meistens nicht „auf NULL setzen").

        Soft-Check: Falls Name oder Kategorie geändert werden, prüfen
        wir wieder auf Duplikate — diesmal aber unter Ausschluss des
        Artikels selbst, damit „kein Namenswechsel" keine falsche
        Warnung erzeugt.
        """
        with get_session() as session:
            artikel = ArtikelDAO.get_by_id(session, artikel_id)
            if artikel is None:
                raise ValueError(f"Artikel mit ID {artikel_id} existiert nicht.")

            # Felder anwenden, die ausdrücklich übergeben wurden.
            if name is not None:
                artikel.name = name
            if kategorie_id is not None:
                # Existenz-Check, sonst gäbe es nur eine FK-IntegrityError.
                if KategorieDAO.get_by_id(session, kategorie_id) is None:
                    raise ValueError(
                        f"Kategorie mit ID {kategorie_id} existiert nicht."
                    )
                artikel.kategorie_id = kategorie_id
            if preis is not None:
                artikel.preis = preis
            if beschreibung is not None:
                artikel.beschreibung = beschreibung
            if bild_url is not None:
                artikel.bild_url = bild_url
            if verfuegbar is not None:
                artikel.verfuegbar = verfuegbar

            warnungen: list[str] = []
            # Soft-Check nur, wenn Name oder Kategorie geändert wurden —
            # sonst ist's irrelevant und wir sparen uns die Query.
            if name is not None or kategorie_id is not None:
                ziel_kategorie = KategorieDAO.get_by_id(
                    session, artikel.kategorie_id
                )
                # ziel_kategorie kann hier nicht None sein (oben geprüft),
                # aber wir setzen einen Fallback für die Typ-Prüfung.
                kategorie_name = ziel_kategorie.name if ziel_kategorie else "?"
                warnungen = ArtikelService._duplikat_pruefen(
                    session=session,
                    name=artikel.name,
                    kategorie_id=artikel.kategorie_id,
                    kategorie_name=kategorie_name,
                    ignoriere_artikel_id=artikel.id,
                )

            aktualisiert = ArtikelDAO.update(session, artikel)
            return ArtikelMitWarnung(artikel=aktualisiert, warnungen=warnungen)

    @staticmethod
    def verfuegbarkeit_umschalten(artikel_id: int) -> Artikel:
        """Toggelt die Verfügbarkeit eines Artikels (verfügbar ↔ nicht).

        Convenience-Methode für den Admin-Schalter „Heute aus".
        Wirft `ValueError`, wenn der Artikel nicht existiert.
        """
        with get_session() as session:
            artikel = ArtikelDAO.get_by_id(session, artikel_id)
            if artikel is None:
                raise ValueError(f"Artikel mit ID {artikel_id} existiert nicht.")
            artikel.verfuegbar = not artikel.verfuegbar
            return ArtikelDAO.update(session, artikel)

    @staticmethod
    def artikel_loeschen(artikel_id: int) -> bool:
        """Löscht einen Artikel.

        Rückgabe:
          - True, falls gelöscht
          - False, falls die ID nicht existierte

        Achtung: Wenn der Artikel schon in `bestellposition` referenziert
        wird, wirft die DB eine IntegrityError (FK-Schutz). Die Page
        sollte das fangen und dem Admin vorschlagen, stattdessen
        `verfuegbarkeit_umschalten` zu nutzen.
        """
        with get_session() as session:
            return ArtikelDAO.delete(session, artikel_id)

    # =======================================================================
    # Standard-Rezept
    # =======================================================================

    @staticmethod
    def rezept_setzen(
        artikel_id: int, zutaten: list[tuple[int, Decimal]]
    ) -> list[ArtikelZutat]:
        """Setzt das Standard-Rezept eines Artikels komplett neu.

        Workflow innerhalb einer Transaktion:
          1. Existenz von Artikel und allen Zutaten prüfen (sonst Abbruch
             vor irgendeiner Mutation).
          2. Bisheriges Rezept löschen.
          3. Neue Zutaten in der gegebenen Reihenfolge eintragen.

        `zutaten` ist eine Liste von Tupeln `(zutat_id, menge)`. Wir
        akzeptieren bewusst Tupel statt Dict, damit die Reihenfolge
        nicht „verloren geht" — auch wenn sie aktuell nicht
        weiterverwendet wird.

        Wirft `ValueError`, wenn Artikel oder eine Zutat nicht existiert.
        Bei einem Fehler mitten in der Transaktion (etwa DB-Konflikt)
        rollt `get_session()` alles zurück — das alte Rezept bleibt damit
        intakt.
        """
        with get_session() as session:
            # Schritt 1: Validierung vor jeder Mutation.
            if ArtikelDAO.get_by_id(session, artikel_id) is None:
                raise ValueError(f"Artikel mit ID {artikel_id} existiert nicht.")
            for zutat_id, _ in zutaten:
                if ZutatDAO.get_by_id(session, zutat_id) is None:
                    raise ValueError(
                        f"Zutat mit ID {zutat_id} existiert nicht."
                    )

            # Schritt 2: Altes Rezept weg.
            ArtikelZutatDAO.rezept_loeschen(session, artikel_id)

            # Schritt 3: Neues Rezept aufbauen.
            for zutat_id, menge in zutaten:
                ArtikelZutatDAO.zutat_hinzufuegen(
                    session, artikel_id, zutat_id, menge
                )

            # Frisch laden — der Aufrufer bekommt das aktuelle Rezept
            # inkl. eager-loaded Zutat-Relation zurück.
            return ArtikelZutatDAO.rezept_laden(session, artikel_id)

    # =======================================================================
    # Kategorien — CRUD (für Admin-Bereich)
    # =======================================================================

    @staticmethod
    def kategorien_alle() -> list[Kategorie]:
        """Liefert alle Kategorien, sortiert nach `sortierung` + `name`.

        Wird im Admin gebraucht (Übersichts-Tabelle) und im Artikel-
        Anlegen-Dialog (Dropdown-Auswahl der Ziel-Kategorie).
        """
        with get_session() as session:
            return KategorieDAO.get_all(session, sortiert=True)

    @staticmethod
    def kategorie_anlegen(
        *,
        name: str,
        beschreibung: Optional[str] = None,
        sortierung: int = 0,
    ) -> Kategorie:
        """Legt eine neue Kategorie an.

        `Kategorie.name` ist im Modell `unique` — wir prüfen das hier
        explizit, damit der Aufrufer eine lesbare Fehlermeldung statt
        einer rohen IntegrityError bekommt.
        """
        with get_session() as session:
            if KategorieDAO.exists(session, name):
                raise ValueError(f"Kategorie '{name}' existiert bereits.")
            kategorie = Kategorie(
                name=name, beschreibung=beschreibung, sortierung=sortierung
            )
            return KategorieDAO.create(session, kategorie)

    @staticmethod
    def kategorie_bearbeiten(
        kategorie_id: int,
        *,
        name: Optional[str] = None,
        beschreibung: Optional[str] = None,
        sortierung: Optional[int] = None,
    ) -> Kategorie:
        """Aktualisiert die übergebenen Felder einer Kategorie.

        Bei Namensänderung erneute Unique-Prüfung — sonst würde der DB-
        Constraint mit einer kryptischen Fehlermeldung knallen.
        Konvention wie bei `artikel_bearbeiten`: `None` heisst „nicht
        ändern".
        """
        with get_session() as session:
            kategorie = KategorieDAO.get_by_id(session, kategorie_id)
            if kategorie is None:
                raise ValueError(
                    f"Kategorie mit ID {kategorie_id} existiert nicht."
                )
            if name is not None and name != kategorie.name:
                if KategorieDAO.exists(session, name):
                    raise ValueError(
                        f"Kategorie '{name}' existiert bereits."
                    )
                kategorie.name = name
            if beschreibung is not None:
                kategorie.beschreibung = beschreibung
            if sortierung is not None:
                kategorie.sortierung = sortierung
            return KategorieDAO.update(session, kategorie)

    @staticmethod
    def kategorie_loeschen(kategorie_id: int) -> bool:
        """Löscht eine Kategorie.

        Achtung: Hängen Artikel an dieser Kategorie, wirft die DB eine
        IntegrityError (FK-Schutz aus `_foreign_keys_aktivieren`).
        Die Page sollte das fangen und dem Admin vorschlagen, die
        Artikel zuerst umzuhängen oder die Kategorie nur zu sortieren.
        """
        with get_session() as session:
            return KategorieDAO.delete(session, kategorie_id)

    # =======================================================================
    # Zutaten — CRUD (für Admin-Bereich)
    # =======================================================================

    @staticmethod
    def zutaten_alle(
        *,
        nur_verfuegbar: bool = False,
        nur_vegetarisch: bool = False,
    ) -> list[Zutat]:
        """Liefert Zutaten, optional gefiltert.

        Im Admin meist mit Default-Flags (= alle), damit man auch
        ausverkaufte Zutaten sieht und wieder einschalten kann.
        Im Wunschpizza-Builder später sinnvoll mit
        `nur_verfuegbar=True`.
        """
        with get_session() as session:
            return ZutatDAO.get_all(
                session,
                nur_verfuegbar=nur_verfuegbar,
                nur_vegetarisch=nur_vegetarisch,
            )

    @staticmethod
    def zutat_anlegen(
        *,
        name: str,
        preis_pro_einheit: Decimal,
        einheit: str = "Portion",
        vegetarisch: bool = True,
        verfuegbar: bool = True,
    ) -> Zutat:
        """Legt eine neue Zutat an.

        `Zutat.name` ist `unique` — wie bei Kategorie prüfen wir das
        explizit, damit die Fehlermeldung lesbar ist statt einer
        rohen IntegrityError.
        """
        with get_session() as session:
            if ZutatDAO.exists(session, name):
                raise ValueError(f"Zutat '{name}' existiert bereits.")
            zutat = Zutat(
                name=name,
                preis_pro_einheit=preis_pro_einheit,
                einheit=einheit,
                vegetarisch=vegetarisch,
                verfuegbar=verfuegbar,
            )
            return ZutatDAO.create(session, zutat)

    @staticmethod
    def zutat_bearbeiten(
        zutat_id: int,
        *,
        name: Optional[str] = None,
        preis_pro_einheit: Optional[Decimal] = None,
        einheit: Optional[str] = None,
        vegetarisch: Optional[bool] = None,
        verfuegbar: Optional[bool] = None,
    ) -> Zutat:
        """Aktualisiert die übergebenen Felder einer Zutat.

        Bei Namensänderung erneute Unique-Prüfung. Konvention wie immer:
        `None` heisst „nicht ändern". Der Preis bleibt frei änderbar —
        ein Snapshot wird in `Bestellposition.einzelpreis` gehalten,
        sodass alte Bestellungen ihre Werte behalten (siehe Modell).
        """
        with get_session() as session:
            zutat = ZutatDAO.get_by_id(session, zutat_id)
            if zutat is None:
                raise ValueError(
                    f"Zutat mit ID {zutat_id} existiert nicht."
                )
            if name is not None and name != zutat.name:
                if ZutatDAO.exists(session, name):
                    raise ValueError(f"Zutat '{name}' existiert bereits.")
                zutat.name = name
            if preis_pro_einheit is not None:
                zutat.preis_pro_einheit = preis_pro_einheit
            if einheit is not None:
                zutat.einheit = einheit
            if vegetarisch is not None:
                zutat.vegetarisch = vegetarisch
            if verfuegbar is not None:
                zutat.verfuegbar = verfuegbar
            return ZutatDAO.update(session, zutat)

    @staticmethod
    def zutat_verfuegbarkeit_umschalten(zutat_id: int) -> Zutat:
        """Toggelt die Verfügbarkeit einer Zutat (Convenience für Admin)."""
        with get_session() as session:
            zutat = ZutatDAO.get_by_id(session, zutat_id)
            if zutat is None:
                raise ValueError(
                    f"Zutat mit ID {zutat_id} existiert nicht."
                )
            aktualisiert = ZutatDAO.verfuegbarkeit_setzen(
                session, zutat_id, verfuegbar=not zutat.verfuegbar
            )
            # `verfuegbarkeit_setzen` gibt None nur zurück, wenn die ID
            # nicht existiert — das haben wir oben aber schon ausgeschlossen.
            assert aktualisiert is not None
            return aktualisiert

    @staticmethod
    def zutat_loeschen(zutat_id: int) -> bool:
        """Löscht eine Zutat.

        Achtung: Wenn die Zutat in `artikel_zutat` (Standard-Rezept)
        oder `wunsch_zutat` (Wunschpizza) referenziert wird, wirft die
        DB eine IntegrityError. Die Page sollte das fangen und
        stattdessen `zutat_verfuegbarkeit_umschalten` vorschlagen.
        """
        with get_session() as session:
            return ZutatDAO.delete(session, zutat_id)

    # =======================================================================
    # Interne Helfer
    # =======================================================================

    @staticmethod
    def _duplikat_pruefen(
        *,
        session,
        name: str,
        kategorie_id: int,
        kategorie_name: str,
        ignoriere_artikel_id: Optional[int],
    ) -> list[str]:
        """Liefert Warnungen für mögliche Namens-Duplikate in der Kategorie.

        Hier in Python (statt SQL) gefiltert, weil:
          - die Liste pro Kategorie klein ist (~10 Artikel)
          - `casefold()` portabler ist als DB-spezifisches case-insensitive
            LIKE
          - wir den Artikel selbst beim Bearbeiten ausschliessen müssen
            (`ignoriere_artikel_id`) — das wäre als zusätzliche WHERE-
            Bedingung möglich, aber so liest sich der Code direkter.
        """
        bestehende = ArtikelDAO.get_nach_kategorie(session, kategorie_id)
        gleicher_name = [
            a for a in bestehende
            if a.name.casefold() == name.casefold()
            and a.id != ignoriere_artikel_id
        ]
        if not gleicher_name:
            return []
        return [
            f"In Kategorie '{kategorie_name}' existiert bereits ein Artikel "
            f"mit dem Namen '{name}'."
        ]
