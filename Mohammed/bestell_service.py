"""
Service — Bestellung & Warenkorb
=================================
Business-Logik rund um Warenkorb und Bestell-Abschluss.

Dieser Service ist die Facade vor:
  - `BestellungDAO` / `BestellpositionDAO` / `ZahlungService`
  - Optional: `QuittungService` (von Irem) — wird via Hook eingebunden,
    sodass mein Code unabhängig läuft, auch wenn Irems Service noch
    nicht fertig ist.

Verantwortlichkeiten:
  - Warenkorb im SPEICHER halten (pro Kunde ein Warenkorb). Beim
    App-Neustart ist er weg — das ist im Studienprojekt ok und spart
    eine eigene DB-Tabelle.
  - Wunschpizza-Items im Warenkorb verwalten (Basis-Artikel + gewählte
    Zutaten + Live-Preis).
  - Mindestbestellwert prüfen.
  - Beim Abschicken: alles in einer Transaktion persistieren
    (Bestellung -> Positionen -> WunschZutaten -> Zahlung -> Quittung).

Design Pattern: Facade. Die Pages reden nur mit dem `BestellService`,
nicht direkt mit den DAOs oder dem `ZahlungService`. So bleibt die UI
schlank und der Bestell-Flow ist an einer Stelle nachvollziehbar.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional

from sqlmodel import Session

from dao.artikel_dao import ArtikelDAO
from dao.bestellposition_dao import BestellpositionDAO
from dao.bestellung_dao import BestellungDAO
from dao.zutat_dao import ZutatDAO
from domain.models import Artikel, Bestellposition, Bestellung, Zutat
from services.zahlung_service import ZahlungService
from utils.db import get_session


# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------


# Mindestbestellwert in CHF. Wenn der Warenkorb darunter liegt, kann
# nicht bestellt werden. Bewusst als Klassen-Konstante / Modul-Konstante,
# damit Irem sie auf der Checkout-Page anzeigen kann.
MINDESTBESTELLWERT: Decimal = Decimal("20.00")


# ---------------------------------------------------------------------------
# Warenkorb-Datenstrukturen (im Speicher, nicht in der DB)
# ---------------------------------------------------------------------------


@dataclass
class WarenkorbItem:
    """Ein Eintrag im Warenkorb.

    Repräsentiert entweder:
      - einen normalen Artikel (`ist_wunschpizza=False`, `zutat_ids=[]`)
      - eine Wunschpizza (`ist_wunschpizza=True`, `zutat_ids` enthält die
        gewählten Zutaten zusätzlich zum Standard-Rezept).

    Die `temp_id` ist eine in-memory ID, die nur im Warenkorb gilt — sie
    erlaubt der UI, eine einzelne Wunschpizza zu identifizieren (Menge
    ändern, entfernen), bevor sie in der DB landet. Sobald der Kunde
    bestellt, bekommt jede Position eine echte `bestellposition_id`.
    """

    temp_id: int
    artikel_id: int
    artikel_name: str  # Snapshot fürs Anzeigen ohne DB-Query
    einzelpreis: Decimal  # Snapshot des Artikel-Preises
    menge: int = 1
    ist_wunschpizza: bool = False
    zutat_ids: list[int] = field(default_factory=list)
    # Snapshot der Zutaten fürs Anzeigen + Preis-Berechnung
    zutat_namen: list[str] = field(default_factory=list)
    zutat_preise: list[Decimal] = field(default_factory=list)
    bemerkung: Optional[str] = None

    def zutaten_preis_pro_pizza(self) -> Decimal:
        """Summe der Zusatz-Zutaten-Preise pro einzelner Pizza."""
        return sum(self.zutat_preise, start=Decimal("0.00"))

    def positionssumme(self) -> Decimal:
        """`menge × (einzelpreis + zutaten_aufschlag)`.

        Identische Logik zu `Bestellposition.positionsbetrag_berechnen()` —
        wir spiegeln sie hier im Warenkorb, damit die UI live rechnen
        kann, ohne die DB anzufragen.
        """
        pro_stueck = self.einzelpreis + self.zutaten_preis_pro_pizza()
        return Decimal(self.menge) * pro_stueck


@dataclass
class WarenkorbInhalt:
    """Alle Items eines Kunden mit Gesamtsumme.

    Wird von `warenkorb_lesen()` zurückgegeben. Die UI kann direkt
    rendern, ohne selbst zu rechnen.
    """

    items: list[WarenkorbItem]
    gesamtsumme: Decimal
    mindestbestellwert: Decimal
    mindestbestellwert_erreicht: bool


@dataclass
class BestellErgebnis:
    """Ergebnis von `bestellung_aufgeben()`.

    Die Page kann nach erfolgreichem Bestellen direkt anzeigen:
      - die ID der frischen Bestellung (z. B. „Ihre Bestellung Nr. 42“)
      - den bezahlten Betrag
      - den Pfad zur Quittung (oder None, falls Irems QuittungService
        noch nicht da ist).
    """

    bestellung_id: int
    gesamtbetrag: Decimal
    quittung_pfad: Optional[str] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BestellService:
    """Facade für Warenkorb und Bestell-Abschluss.

    Warenkorb-Storage: in-memory Dict, Key = `kunden_id`. Jeder Kunde
    hat genau einen Warenkorb. Beim App-Restart sind alle Warenkörbe
    weg — bewusst, weil eine eigene Warenkorb-Tabelle im Studienprojekt
    Overkill wäre.
    """

    # Klassen-Konstante, damit Pages sie ohne Import-Spaghetti lesen können
    MINDESTBESTELLWERT: Decimal = MINDESTBESTELLWERT

    # In-Memory-Speicher. Klassen-Attribut, damit ein einziger Warenkorb
    # pro Kunde existiert (statt einem pro Service-Instanz). `_` davor =
    # "intern", nicht von aussen direkt anfassen.
    _waren_koerbe: dict[int, list[WarenkorbItem]] = {}

    # Zähler für `temp_id` — fortlaufend, global. Nutzen wir, damit sich
    # die in-memory IDs nicht überschneiden.
    _temp_id_zaehler = itertools.count(start=1)

    # Hook für den QuittungService. Wird einmalig in `app.py` gesetzt,
    # sobald Irems Service da ist:
    #     BestellService.quittung_hook = QuittungService.quittung_erzeugen
    # Solange `None`, wird einfach keine Quittung erzeugt — der Bestell-
    # Flow läuft trotzdem durch.
    quittung_hook: Optional[Callable[[Session, int], str]] = None

    # =======================================================================
    # Warenkorb — Lesen
    # =======================================================================

    @classmethod
    def warenkorb_lesen(cls, kunden_id: int) -> WarenkorbInhalt:
        """Liefert den aktuellen Warenkorb eines Kunden inkl. Gesamtsumme.

        Wenn der Kunde noch keinen Warenkorb hat, kommt eine leere
        Inhalts-Struktur zurück (kein None) — die UI kann immer dieselben
        Felder lesen.
        """
        items = cls._waren_koerbe.get(kunden_id, [])
        gesamt = sum(
            (item.positionssumme() for item in items),
            start=Decimal("0.00"),
        )
        return WarenkorbInhalt(
            items=list(items),  # Kopie, damit Aufrufer nicht direkt mutieren
            gesamtsumme=gesamt,
            mindestbestellwert=MINDESTBESTELLWERT,
            mindestbestellwert_erreicht=gesamt >= MINDESTBESTELLWERT,
        )

    @classmethod
    def warenkorb_anzahl_items(cls, kunden_id: int) -> int:
        """Anzahl unterschiedlicher Items (nicht Mengen-Summe).

        Praktisch für das kleine Badge am Warenkorb-Icon im Header.
        """
        return len(cls._waren_koerbe.get(kunden_id, []))

    # =======================================================================
    # Warenkorb — Schreiben (normale Artikel)
    # =======================================================================

    @classmethod
    def artikel_hinzufuegen(
        cls, kunden_id: int, artikel_id: int, menge: int = 1
    ) -> WarenkorbItem:
        """Fügt einen normalen Artikel (keine Wunschpizza) zum Warenkorb.

        Wenn derselbe Artikel schon im Warenkorb ist und KEIN Wunschpizza-
        Item ist, erhöhen wir nur die Menge. Wunschpizzas zählen als
        eigene Items, weil verschiedene Wunschpizzas verschiedene Zutaten
        haben können — die zu mergen wäre verwirrend.

        Wirft `ValueError`, wenn der Artikel nicht existiert oder nicht
        verfügbar ist.
        """
        if menge <= 0:
            raise ValueError("Menge muss grösser als 0 sein.")

        with get_session() as session:
            artikel = ArtikelDAO.get_by_id(session, artikel_id)
            if artikel is None:
                raise ValueError(f"Artikel mit ID {artikel_id} existiert nicht.")
            if not artikel.verfuegbar:
                raise ValueError(
                    f"Artikel „{artikel.name}“ ist aktuell nicht verfügbar."
                )

            # Snapshot der Artikel-Daten ziehen, BEVOR die Session zugeht —
            # innerhalb des with-Blocks sind die Daten garantiert frisch.
            artikel_name = artikel.name
            einzelpreis = artikel.preis

        # Bereits vorhandenes (nicht-Wunschpizza-)Item suchen
        koerbe = cls._waren_koerbe.setdefault(kunden_id, [])
        for vorhandenes in koerbe:
            if (
                vorhandenes.artikel_id == artikel_id
                and not vorhandenes.ist_wunschpizza
            ):
                vorhandenes.menge += menge
                return vorhandenes

        # Neues Item anlegen
        neues_item = WarenkorbItem(
            temp_id=next(cls._temp_id_zaehler),
            artikel_id=artikel_id,
            artikel_name=artikel_name,
            einzelpreis=einzelpreis,
            menge=menge,
        )
        koerbe.append(neues_item)
        return neues_item

    # =======================================================================
    # Warenkorb — Schreiben (Wunschpizza)
    # =======================================================================

    @classmethod
    def wunschpizza_hinzufuegen(
        cls,
        kunden_id: int,
        basis_artikel_id: int,
        zutat_ids: list[int],
        menge: int = 1,
        bemerkung: Optional[str] = None,
    ) -> WarenkorbItem:
        """Legt eine Wunschpizza in den Warenkorb.

        `basis_artikel_id` ist die Pizza, die als Basis dient (z. B.
        „Pizza Margherita“ mit ihrem Standard-Rezept). `zutat_ids` sind
        die ZUSÄTZLICH gewählten Zutaten — sie kommen oben drauf.

        Wirft `ValueError`, wenn Artikel oder eine Zutat nicht existiert
        oder nicht verfügbar ist.
        """
        if menge <= 0:
            raise ValueError("Menge muss grösser als 0 sein.")

        with get_session() as session:
            artikel = ArtikelDAO.get_by_id(session, basis_artikel_id)
            if artikel is None:
                raise ValueError(
                    f"Basis-Artikel mit ID {basis_artikel_id} existiert nicht."
                )
            if not artikel.verfuegbar:
                raise ValueError(
                    f"Basis-Artikel „{artikel.name}“ ist nicht verfügbar."
                )

            # Snapshots ziehen
            artikel_name = artikel.name
            einzelpreis = artikel.preis

            # Zutaten laden und validieren
            zutat_namen: list[str] = []
            zutat_preise: list[Decimal] = []
            for zutat_id in zutat_ids:
                zutat = ZutatDAO.get_by_id(session, zutat_id)
                if zutat is None:
                    raise ValueError(
                        f"Zutat mit ID {zutat_id} existiert nicht."
                    )
                if not zutat.verfuegbar:
                    raise ValueError(
                        f"Zutat „{zutat.name}“ ist aktuell nicht verfügbar."
                    )
                zutat_namen.append(zutat.name)
                zutat_preise.append(zutat.preis_pro_einheit)

        # Wunschpizzas immer als NEUES Item — auch wenn die Zutaten
        # identisch sind. Das hält die UI vorhersagbar (sonst müsste der
        # Kunde rätseln, ob seine zweite Wunschpizza zur ersten dazu-
        # geschlagen wird).
        neues_item = WarenkorbItem(
            temp_id=next(cls._temp_id_zaehler),
            artikel_id=basis_artikel_id,
            artikel_name=f"Wunschpizza ({artikel_name})",
            einzelpreis=einzelpreis,
            menge=menge,
            ist_wunschpizza=True,
            zutat_ids=list(zutat_ids),
            zutat_namen=zutat_namen,
            zutat_preise=zutat_preise,
            bemerkung=bemerkung,
        )
        cls._waren_koerbe.setdefault(kunden_id, []).append(neues_item)
        return neues_item

    # =======================================================================
    # Warenkorb — Ändern / Entfernen
    # =======================================================================

    @classmethod
    def menge_aendern(
        cls, kunden_id: int, temp_id: int, neue_menge: int
    ) -> Optional[WarenkorbItem]:
        """Ändert die Menge eines Items im Warenkorb.

        - `neue_menge <= 0` ist gleichbedeutend mit „entfernen“. Statt
          eine Exception zu werfen, sind wir hier nett: das Item
          verschwindet einfach. Die UI muss sich nicht zwischen „Menge
          setzen" und „Item entfernen“ entscheiden.
        - Gibt das aktualisierte Item zurück, oder `None` wenn die
          temp_id nicht (mehr) existiert.
        """
        koerbe = cls._waren_koerbe.get(kunden_id, [])
        for item in koerbe:
            if item.temp_id == temp_id:
                if neue_menge <= 0:
                    koerbe.remove(item)
                    return None
                item.menge = neue_menge
                return item
        return None

    @classmethod
    def item_entfernen(cls, kunden_id: int, temp_id: int) -> bool:
        """Entfernt ein Item aus dem Warenkorb.

        Rückgabe:
          - True, falls entfernt
          - False, falls die temp_id nicht (mehr) existiert.
        """
        koerbe = cls._waren_koerbe.get(kunden_id, [])
        for item in koerbe:
            if item.temp_id == temp_id:
                koerbe.remove(item)
                return True
        return False

    @classmethod
    def warenkorb_leeren(cls, kunden_id: int) -> None:
        """Entfernt alle Items aus dem Warenkorb eines Kunden.

        Wird nach erfolgreichem Bestellen automatisch aufgerufen — der
        Kunde startet seine nächste Bestellung mit einem leeren Korb.
        """
        cls._waren_koerbe.pop(kunden_id, None)

    # =======================================================================
    # Bestellung aufgeben (der grosse Flow)
    # =======================================================================

    @classmethod
    def bestellung_aufgeben(
        cls,
        kunden_id: int,
        lieferadresse_id: int,
        zahlungsmethode: str = "karte",
        bemerkung: Optional[str] = None,
    ) -> BestellErgebnis:
        """Schliesst die Bestellung ab — die Hauptmethode der Facade.

        Workflow (ALLES in einer Transaktion):
          1. Warenkorb laden + validieren (nicht leer, Mindestbestellwert)
          2. `Bestellung` anlegen (mit gesamtbetrag=0, kommt gleich)
          3. Pro WarenkorbItem eine `Bestellposition` anlegen
          4. Pro Wunschpizza die `WunschZutat`-Einträge anlegen
          5. `gesamtbetrag` auf der Bestellung aktualisieren
          6. `ZahlungService.zahlung_durchfuehren()` aufrufen
          7. Optional: `quittung_hook` aufrufen (Irems QuittungService)
          8. Warenkorb leeren

        Bei einem Fehler in Schritt 2-7 rollt `get_session()` alles
        zurück — keine halben Bestellungen, keine verwaisten Positionen.

        Wirft:
          - `ValueError` bei leerem Warenkorb oder zu niedrigem Betrag
          - SQLAlchemy-Exceptions, wenn die FK-Constraints (Kunde,
            Adresse) nicht passen. Die Page sollte das fangen und eine
            UI-Meldung zeigen.
        """
        inhalt = cls.warenkorb_lesen(kunden_id)
        if not inhalt.items:
            raise ValueError("Der Warenkorb ist leer.")
        if not inhalt.mindestbestellwert_erreicht:
            raise ValueError(
                f"Mindestbestellwert von CHF {MINDESTBESTELLWERT:.2f} "
                f"nicht erreicht (aktuell: CHF {inhalt.gesamtsumme:.2f})."
            )

        with get_session() as session:
            # --- Schritt 2: Bestellung anlegen ---
            bestellung = Bestellung(
                kunden_id=kunden_id,
                lieferadresse_id=lieferadresse_id,
                bemerkung=bemerkung,
                # gesamtbetrag wird unten nach den Positionen gesetzt
            )
            bestellung = BestellungDAO.create(session, bestellung)
            assert bestellung.id is not None  # nach create() garantiert

            # --- Schritt 3 + 4: Positionen + Wunsch-Zutaten ---
            for item in inhalt.items:
                position = Bestellposition(
                    bestellung_id=bestellung.id,
                    artikel_id=item.artikel_id,
                    menge=item.menge,
                    einzelpreis=item.einzelpreis,  # Snapshot
                    ist_wunschpizza=item.ist_wunschpizza,
                    bemerkung=item.bemerkung,
                )
                position = BestellpositionDAO.create(session, position)
                assert position.id is not None

                # Wunsch-Zutaten dranhängen, falls es eine Wunschpizza ist
                if item.ist_wunschpizza:
                    for zutat_id in item.zutat_ids:
                        BestellpositionDAO.wunsch_zutat_hinzufuegen(
                            session,
                            bestellposition_id=position.id,
                            zutat_id=zutat_id,
                        )

            # --- Schritt 5: Gesamtbetrag eintragen ---
            # Wir nehmen die Summe aus dem Warenkorb (gleicher
            # Berechnungsweg wie bei `positionsbetrag_berechnen()`).
            bestellung.gesamtbetrag = inhalt.gesamtsumme
            BestellungDAO.update(session, bestellung)

            # --- Schritt 6: Zahlung ---
            ZahlungService.zahlung_durchfuehren(
                session=session,
                bestellung_id=bestellung.id,
                betrag=inhalt.gesamtsumme,
                zahlungsmethode=zahlungsmethode,
            )

            # --- Schritt 7: Quittung (optional, via Hook) ---
            quittung_pfad: Optional[str] = None
            if cls.quittung_hook is not None:
                try:
                    quittung_pfad = cls.quittung_hook(session, bestellung.id)
                except Exception as e:
                    # Wenn die Quittungs-Erzeugung scheitert, rollen wir
                    # NICHT die ganze Bestellung zurück — sie ist gültig
                    # und bezahlt. Stattdessen loggen und ohne PDF
                    # weitermachen. Irems Service kann später noch eine
                    # Quittung nachträglich erzeugen.
                    print(
                        f"[WARN] Quittung konnte nicht erzeugt werden: {e}"
                    )

            # Schnapp den finalen Betrag, bevor die Session zugeht
            finaler_betrag = bestellung.gesamtbetrag
            bestellung_id_final = bestellung.id

        # --- Schritt 8: Warenkorb leeren (ausserhalb der DB-Transaktion) ---
        cls.warenkorb_leeren(kunden_id)

        return BestellErgebnis(
            bestellung_id=bestellung_id_final,
            gesamtbetrag=finaler_betrag,
            quittung_pfad=quittung_pfad,
        )
