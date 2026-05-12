"""
Page — /menu
=============
Kunden-Menü: Alle verfügbaren Kategorien mit ihren Artikeln.

Verantwortlichkeiten:
  - UI rendern (NiceGUI-Komponenten)
  - Daten vom `ArtikelService` holen — KEIN direkter DAO- oder DB-
    Zugriff, KEIN SQL hier drin.
  - Auf Klicks reagieren (aktuell nur Refresh + Warenkorb-Hook).

Kein Verhalten in dieser Datei, das nicht zur UI gehört. Validierungen,
Datenaggregation und Business-Regeln laufen ausschliesslich im Service.

Status der Warenkorb-Integration:
  Der „In den Warenkorb“-Button ist aktuell ein Platzhalter, weil
  Mohammeds `BestellService` noch nicht steht. Sobald er die Funktion
  zur Verfügung stellt, wird der Aufruf in `_artikel_in_warenkorb_legen`
  ersetzt — alle anderen Stellen in dieser Datei bleiben unverändert.
"""

from __future__ import annotations

from nicegui import ui

from domain.models import Artikel
from services.artikel_service import ArtikelService, MenueEintrag


# ---------------------------------------------------------------------------
# Page-Routing
# ---------------------------------------------------------------------------


@ui.page("/menu")
def menue_seite() -> None:
    """Einstiegspunkt für die Route `/menu`.

    NiceGUI ruft diese Funktion bei jedem Page-Load erneut auf — also
    wird auch das Menü bei jedem Aufruf frisch aus der DB geladen. Das
    ist gewollt: Wenn der Admin im anderen Tab eine Pizza ausverkauft
    setzt, sieht der Kunde das beim nächsten Reload sofort.
    """
    _kopfzeile()
    _menue_inhalt()


# ---------------------------------------------------------------------------
# UI-Bausteine
# ---------------------------------------------------------------------------


def _kopfzeile() -> None:
    """Header der Seite — Titel und Refresh-Button.

    Bewusst klein gehalten: Branding/Navigation kommt später, wenn die
    Pages des Teams alle stehen und wir ein gemeinsames Layout-Modul
    bauen.
    """
    with ui.row().classes("w-full items-center justify-between p-4"):
        ui.label("Pizzeria Sunshine — Menü").classes("text-2xl font-bold")
        # Refresh ist trivial implementierbar via ui.navigate.reload(),
        # weil unser Page-Body bei jedem Reload frisch lädt (siehe oben).
        ui.button(icon="refresh", on_click=lambda: ui.navigate.reload()).props(
            "flat"
        ).tooltip("Menü neu laden")


def _menue_inhalt() -> None:
    """Lädt das Menü vom Service und rendert es."""
    menue: list[MenueEintrag] = ArtikelService.menue_laden(nur_verfuegbar=True)

    if not menue:
        # Leerer Zustand: lieber eine freundliche Meldung als eine leere Seite.
        with ui.column().classes("w-full items-center p-8"):
            ui.label("Aktuell sind keine Artikel verfügbar.").classes(
                "text-lg text-gray-600"
            )
        return

    # Pro Kategorie eine eigene Sektion (Heading + Artikel-Grid).
    with ui.column().classes("w-full p-4 gap-6"):
        for eintrag in menue:
            _kategorie_sektion(eintrag)


def _kategorie_sektion(eintrag: MenueEintrag) -> None:
    """Rendert eine Kategorie-Überschrift und ein Grid mit Artikel-Karten."""
    with ui.column().classes("w-full gap-2"):
        ui.label(eintrag.kategorie.name).classes("text-xl font-semibold")
        if eintrag.kategorie.beschreibung:
            ui.label(eintrag.kategorie.beschreibung).classes(
                "text-sm text-gray-600"
            )
        # Responsives Grid: schmaler Bildschirm = 1 Spalte,
        # mittlerer = 2, breiter = 3. Das hält das Menü auf Handy lesbar.
        with ui.grid(columns="repeat(auto-fill, minmax(280px, 1fr))").classes(
            "w-full gap-4"
        ):
            for artikel in eintrag.artikel:
                _artikel_karte(artikel)


def _artikel_karte(artikel: Artikel) -> None:
    """Eine einzelne Artikel-Karte (Name, Beschreibung, Preis, Button)."""
    with ui.card().classes("w-full"):
        with ui.column().classes("w-full gap-1"):
            ui.label(artikel.name).classes("text-lg font-semibold")
            if artikel.beschreibung:
                ui.label(artikel.beschreibung).classes(
                    "text-sm text-gray-700"
                )
            # Preis und Button in einer Zeile — Preis links, Button rechts.
            with ui.row().classes("w-full items-center justify-between mt-2"):
                # Decimal über f-string mit fester Stellenzahl.
                # `:.2f` formatiert auf 2 Nachkommastellen, locale-frei.
                ui.label(f"CHF {artikel.preis:.2f}").classes("text-base")
                ui.button(
                    "In den Warenkorb",
                    on_click=lambda a=artikel: _artikel_in_warenkorb_legen(a),
                ).props("color=primary")


# ---------------------------------------------------------------------------
# Warenkorb-Hook (Platzhalter — wird von Mohammed gefüllt)
# ---------------------------------------------------------------------------


def _artikel_in_warenkorb_legen(artikel: Artikel) -> None:
    """Platzhalter, bis Mohammeds `BestellService` da ist.

    Sobald sein Service steht, wird hier nur diese eine Zeile getauscht
    — z. B.:
        from services.bestell_service import BestellService
        BestellService.warenkorb_artikel_hinzufuegen(artikel.id, menge=1)
        ui.notify(f"„{artikel.name}“ zum Warenkorb hinzugefügt", type="positive")

    Solange das nicht da ist, geben wir nur eine sichtbare Rückmeldung,
    damit die UI demonstrierbar ist und niemand auf einen toten Button
    klickt.
    """
    # TODO(Mohammed): Hier `BestellService.warenkorb_artikel_hinzufuegen(...)`
    # aufrufen, sobald der `BestellService` existiert. Diese Datei selbst
    # muss dafür sonst nicht angefasst werden.
    ui.notify(
        f"„{artikel.name}“ — Warenkorb-Funktion folgt (Mohammeds BestellService).",
        type="info",
    )
