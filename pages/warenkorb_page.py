"""
Page — /warenkorb
==================
Warenkorb-Übersicht und Wunschpizza-Builder.

Funktionen:
  - Alle Items im Warenkorb anzeigen
  - Menge ändern (+/-)
  - Items entfernen
  - Wunschpizza zusammenstellen (Basis-Pizza wählen + Zutaten anklicken)
  - Button „Zur Kasse“ -> Navigation zu /checkout

Wie Younus' menu_page.py: KEIN direkter DAO/SQL-Zugriff hier — alles
läuft über `BestellService` (für Warenkorb) und `ArtikelService` (um
Pizza-Liste und Zutaten zu laden, ohne DAOs zu importieren).

Login-Status:
  Wir brauchen einen Kunden, dem der Warenkorb „gehört“. Solange Irems
  AuthService nicht da ist, nimmt `_aktuelle_kunden_id()` einen Demo-
  Kunden — mit deutlicher Warnung in der UI. Sobald sein Service da ist,
  wird nur diese eine Funktion angepasst.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from nicegui import ui

from domain.models import Artikel, Zutat
from services.artikel_service import ArtikelService
from services.bestell_service import BestellService, WarenkorbItem
from utils.db import get_session
from dao.artikel_dao import ArtikelDAO
from dao.kategorie_dao import KategorieDAO
from dao.zutat_dao import ZutatDAO


# ---------------------------------------------------------------------------
# Login-Stub (wird ersetzt, sobald Irems AuthService da ist)
# ---------------------------------------------------------------------------


# Demo-Kunden-ID, solange kein echter Login existiert. Sobald Irems
# AuthService da ist, lesen wir die ID stattdessen aus der Session — z. B.:
#     from services.auth_service import AuthService
#     return AuthService.aktuelle_kunden_id()
_DEMO_KUNDEN_ID = 1


def _aktuelle_kunden_id() -> int:
    """Liefert die ID des eingeloggten Kunden.

    Aktuell: Fallback auf Demo-Kunde (ID 1). Sobald Irems AuthService
    steht, wird hier auf `AuthService.aktuelle_kunden_id()` umgestellt
    — keine andere Stelle in dieser Datei muss dann angefasst werden.
    """
    return _DEMO_KUNDEN_ID


# ---------------------------------------------------------------------------
# Page-Routing
# ---------------------------------------------------------------------------


@ui.page("/warenkorb")
def warenkorb_seite() -> None:
    """Einstiegspunkt für `/warenkorb`.

    NiceGUI ruft die Funktion bei jedem Page-Load — also bauen wir bei
    jedem Reload die UI frisch auf. Die `ui.refreshable`-Funktionen
    weiter unten machen partielles Refresh möglich, ohne dass der Kunde
    die ganze Seite neu lädt.
    """
    _kopfzeile()
    _login_warnung_falls_demo()
    _warenkorb_block.refresh()  # baut Liste + Summe
    ui.separator()
    _wunschpizza_builder()


# ---------------------------------------------------------------------------
# Kopf
# ---------------------------------------------------------------------------


def _kopfzeile() -> None:
    """Header — Titel und Link zurück zum Menü."""
    with ui.row().classes("w-full items-center justify-between p-4"):
        ui.label("Warenkorb").classes("text-2xl font-bold")
        ui.button("Zum Menü", on_click=lambda: ui.navigate.to("/menu")).props(
            "flat"
        )


def _login_warnung_falls_demo() -> None:
    """Zeigt einen Hinweis, dass der Demo-Kunde benutzt wird.

    Sobald Irems AuthService da ist, fliegt diese Funktion raus bzw.
    wird einfach nicht mehr aufgerufen.
    """
    ui.notify(
        f"Demo-Modus: Warenkorb gehört zu Kunde {_DEMO_KUNDEN_ID} "
        f"(bis AuthService steht).",
        type="info",
        position="top",
    )


# ---------------------------------------------------------------------------
# Warenkorb-Liste (refreshable, damit +/-/Entfernen sofort wirkt)
# ---------------------------------------------------------------------------


@ui.refreshable
def _warenkorb_block() -> None:
    """Rendert die Warenkorb-Liste + Summen-Zeile + Button „Zur Kasse“."""
    inhalt = BestellService.warenkorb_lesen(_aktuelle_kunden_id())

    if not inhalt.items:
        with ui.column().classes("w-full items-center p-8"):
            ui.label("Dein Warenkorb ist leer.").classes(
                "text-lg text-gray-600"
            )
            ui.button(
                "Zum Menü", on_click=lambda: ui.navigate.to("/menu")
            ).props("color=primary")
        return

    # Liste der Items
    with ui.column().classes("w-full gap-2 p-4"):
        for item in inhalt.items:
            _warenkorb_zeile(item)

    # Summen-Bereich
    with ui.column().classes("w-full p-4 gap-2"):
        ui.separator()
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Zwischensumme").classes("text-base")
            ui.label(f"CHF {inhalt.gesamtsumme:.2f}").classes(
                "text-base font-semibold"
            )
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Mindestbestellwert").classes("text-sm text-gray-600")
            ui.label(f"CHF {inhalt.mindestbestellwert:.2f}").classes(
                "text-sm text-gray-600"
            )

        if not inhalt.mindestbestellwert_erreicht:
            fehlt = inhalt.mindestbestellwert - inhalt.gesamtsumme
            ui.label(
                f"Es fehlen noch CHF {fehlt:.2f} bis zum Mindestbestellwert."
            ).classes("text-sm text-red-600")

        # Button „Zur Kasse" — deaktiviert, solange der Mindestbestellwert
        # nicht erreicht ist. Wir setzen den Zustand statisch (kein Binding):
        # bei jedem Mengen-Change wird `_warenkorb_block.refresh()` aufgerufen,
        # also wird der Button beim nächsten Render neu gebaut — das reicht.
        kasse_btn = ui.button(
            "Zur Kasse",
            on_click=lambda: ui.navigate.to("/checkout"),
        ).props("color=primary size=lg")
        if not inhalt.mindestbestellwert_erreicht:
            kasse_btn.disable()


def _warenkorb_zeile(item: WarenkorbItem) -> None:
    """Eine einzelne Zeile in der Warenkorb-Liste."""
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between gap-4"):
            # Linker Block: Name + Zutaten + Bemerkung
            with ui.column().classes("flex-1 gap-1"):
                ui.label(item.artikel_name).classes("text-lg font-semibold")
                if item.ist_wunschpizza and item.zutat_namen:
                    zutaten_text = "Zutaten: " + ", ".join(item.zutat_namen)
                    ui.label(zutaten_text).classes(
                        "text-sm text-gray-700"
                    )
                if item.bemerkung:
                    ui.label(f"„{item.bemerkung}“").classes(
                        "text-xs text-gray-500 italic"
                    )
                # Einzelpreis-Info, hilft beim Verständnis der Summe
                if item.ist_wunschpizza and item.zutaten_preis_pro_pizza() > 0:
                    ui.label(
                        f"CHF {item.einzelpreis:.2f} "
                        f"+ CHF {item.zutaten_preis_pro_pizza():.2f} Zutaten"
                    ).classes("text-xs text-gray-500")
                else:
                    ui.label(f"CHF {item.einzelpreis:.2f} pro Stück").classes(
                        "text-xs text-gray-500"
                    )

            # Mittlerer Block: Mengen-Steuerung
            with ui.row().classes("items-center gap-1"):
                ui.button(
                    icon="remove",
                    on_click=lambda i=item: _menge_aendern(i.temp_id, -1),
                ).props("dense flat")
                ui.label(str(item.menge)).classes("text-base w-6 text-center")
                ui.button(
                    icon="add",
                    on_click=lambda i=item: _menge_aendern(i.temp_id, +1),
                ).props("dense flat")

            # Rechter Block: Positions-Summe + Entfernen-Button
            with ui.column().classes("items-end gap-1"):
                ui.label(f"CHF {item.positionssumme():.2f}").classes(
                    "text-base font-semibold"
                )
                ui.button(
                    icon="delete",
                    on_click=lambda i=item: _entfernen(i.temp_id),
                ).props("dense flat color=negative")


def _menge_aendern(temp_id: int, delta: int) -> None:
    """Erhöht/verringert die Menge eines Items um `delta`."""
    inhalt = BestellService.warenkorb_lesen(_aktuelle_kunden_id())
    # Aktuelle Menge finden, neu berechnen, setzen.
    # `menge_aendern()` entfernt das Item automatisch, wenn neue Menge <= 0.
    for item in inhalt.items:
        if item.temp_id == temp_id:
            BestellService.menge_aendern(
                _aktuelle_kunden_id(), temp_id, item.menge + delta
            )
            break
    _warenkorb_block.refresh()


def _entfernen(temp_id: int) -> None:
    """Entfernt ein Item komplett aus dem Warenkorb."""
    BestellService.item_entfernen(_aktuelle_kunden_id(), temp_id)
    _warenkorb_block.refresh()


# ---------------------------------------------------------------------------
# Wunschpizza-Builder
# ---------------------------------------------------------------------------


# Modul-Variablen für die Auswahl im Builder. Bewusst Modul-Scope und
# nicht innerhalb der UI-Funktion, damit die Werte über Klicks hinweg
# erhalten bleiben (NiceGUI baut die Page-Funktion bei jedem Reload neu
# auf — Closure-State würde dabei verloren gehen).
_builder_basis_artikel_id: Optional[int] = None
_builder_zutat_ids: set[int] = set()


def _wunschpizza_builder() -> None:
    """Block, in dem der Kunde seine eigene Pizza zusammenstellt.

    Ablauf:
      1. Basis-Pizza wählen (Dropdown)
      2. Zutaten anklicken (Toggle)
      3. Live-Preis sehen
      4. Button „In den Warenkorb“ -> wird als Wunschpizza ergänzt.
    """
    with ui.column().classes("w-full p-4 gap-3"):
        ui.label("Wunschpizza zusammenstellen").classes(
            "text-xl font-bold"
        )
        ui.label(
            "Wähle eine Basis-Pizza und füge beliebige Zutaten hinzu. "
            "Die Standard-Zutaten der gewählten Pizza sind bereits drin "
            "— deine Auswahl kommt obendrauf."
        ).classes("text-sm text-gray-700")

        # Daten holen: Pizzen + verfügbare Zutaten
        pizzas, zutaten = _wunschpizza_daten_laden()

        if not pizzas:
            ui.label(
                "Keine Pizzen im Menü vorhanden. Bitte erst über das Menü "
                "anlegen (Admin)."
            ).classes("text-sm text-red-600")
            return
        if not zutaten:
            ui.label(
                "Keine Zutaten vorhanden. Bitte erst über das Menü anlegen "
                "(Admin)."
            ).classes("text-sm text-red-600")
            return

        # Basis-Pizza-Auswahl (Dropdown)
        pizza_optionen = {p.id: f"{p.name} (CHF {p.preis:.2f})" for p in pizzas}
        # Falls noch keine Auswahl: erste Pizza vor-auswählen
        global _builder_basis_artikel_id
        if (
            _builder_basis_artikel_id is None
            or _builder_basis_artikel_id not in pizza_optionen
        ):
            _builder_basis_artikel_id = next(iter(pizza_optionen.keys()))

        ui.select(
            options=pizza_optionen,
            value=_builder_basis_artikel_id,
            label="Basis-Pizza",
            on_change=lambda e: _basis_setzen(e.value),
        ).classes("w-full max-w-md")

        # Zutaten-Auswahl als anklickbare Chips
        ui.label("Zutaten").classes("text-base font-semibold mt-2")
        with ui.row().classes("flex-wrap gap-2"):
            for zutat in zutaten:
                _zutat_chip(zutat)

        # Live-Preis-Anzeige
        _builder_preis_anzeige.refresh()

        # Button
        ui.button(
            "In den Warenkorb",
            on_click=_wunschpizza_in_warenkorb,
        ).props("color=primary size=lg")


def _wunschpizza_daten_laden() -> tuple[list[Artikel], list[Zutat]]:
    """Holt Pizzen (Artikel der Kategorie „Pizza“) und verfügbare Zutaten.

    Wir suchen die Pizza-Kategorie über den Namen. Falls eine Pizzeria
    eine andere Bezeichnung wählt, würde man das später konfigurierbar
    machen — für unser Studienprojekt reicht's hart codiert.
    """
    with get_session() as session:
        pizza_kategorie = KategorieDAO.get_by_name(session, "Pizza")
        if pizza_kategorie is None or pizza_kategorie.id is None:
            return [], []
        pizzas = ArtikelDAO.get_nach_kategorie(
            session, pizza_kategorie.id, nur_verfuegbar=True
        )
        zutaten = ZutatDAO.get_all(session, nur_verfuegbar=True)
        return pizzas, zutaten


def _basis_setzen(neue_id: int) -> None:
    """Speichert die Auswahl der Basis-Pizza und triggert Preis-Refresh."""
    global _builder_basis_artikel_id
    _builder_basis_artikel_id = neue_id
    _builder_preis_anzeige.refresh()


def _zutat_chip(zutat: Zutat) -> None:
    """Eine anklickbare Zutat als „Chip“ (toggle)."""
    angeklickt = zutat.id in _builder_zutat_ids
    label = f"{zutat.name} (+CHF {zutat.preis_pro_einheit:.2f})"
    btn = ui.button(
        label,
        on_click=lambda z=zutat: _zutat_toggeln(z.id),
    )
    # „angeklickt“ mit Primärfarbe markieren, sonst flat/outline
    if angeklickt:
        btn.props("color=primary")
    else:
        btn.props("outline color=primary")


def _zutat_toggeln(zutat_id: Optional[int]) -> None:
    """Fügt eine Zutat zur Auswahl hinzu / entfernt sie wieder."""
    if zutat_id is None:
        return
    if zutat_id in _builder_zutat_ids:
        _builder_zutat_ids.remove(zutat_id)
    else:
        _builder_zutat_ids.add(zutat_id)
    # Komplette Page-Komponente neu — sonst sehen wir die Chip-Farbe
    # nicht aktualisiert. Etwas grob, aber einfach und schnell genug.
    ui.navigate.reload()


@ui.refreshable
def _builder_preis_anzeige() -> None:
    """Zeigt den aktuellen Wunschpizza-Preis live an."""
    if _builder_basis_artikel_id is None:
        return
    with get_session() as session:
        artikel = ArtikelDAO.get_by_id(session, _builder_basis_artikel_id)
        if artikel is None:
            return
        basis_preis = artikel.preis
        zutaten_summe = Decimal("0.00")
        for zid in _builder_zutat_ids:
            z = ZutatDAO.get_by_id(session, zid)
            if z is not None:
                zutaten_summe += z.preis_pro_einheit
    gesamt = basis_preis + zutaten_summe
    ui.label(
        f"Aktueller Preis: CHF {gesamt:.2f} "
        f"(Basis {basis_preis:.2f} + Zutaten {zutaten_summe:.2f})"
    ).classes("text-base font-semibold mt-2")


def _wunschpizza_in_warenkorb() -> None:
    """Legt die zusammengestellte Wunschpizza in den Warenkorb."""
    if _builder_basis_artikel_id is None:
        ui.notify("Bitte zuerst eine Basis-Pizza wählen.", type="warning")
        return
    try:
        BestellService.wunschpizza_hinzufuegen(
            kunden_id=_aktuelle_kunden_id(),
            basis_artikel_id=_builder_basis_artikel_id,
            zutat_ids=list(_builder_zutat_ids),
            menge=1,
        )
    except ValueError as e:
        ui.notify(str(e), type="negative")
        return

    ui.notify("Wunschpizza in den Warenkorb gelegt.", type="positive")
    # Auswahl zurücksetzen, damit der Kunde gleich eine neue bauen kann
    _builder_zutat_ids.clear()
    _warenkorb_block.refresh()
    _builder_preis_anzeige.refresh()
