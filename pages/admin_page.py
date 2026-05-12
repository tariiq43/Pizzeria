"""
Page — /admin
==============
Admin-Bereich für das Menü: Artikel, Kategorien, Zutaten verwalten.

Verantwortlichkeiten:
  - UI rendern (NiceGUI-Komponenten)
  - Daten ausschliesslich vom `ArtikelService` holen — kein direkter
    DAO-Aufruf, kein SQL.
  - CRUD-Dialoge zeigen, Eingaben validieren (Format) und an den
    Service weiterreichen.
  - Soft-Warnungen vom Service als UI-Notification anzeigen.

Aufbau:
  - Drei Tabs: „Artikel“, „Kategorien“, „Zutaten“ (in dieser Reihenfolge,
    weil der Admin meist Artikel verwaltet und Kategorien/Zutaten nur
    selten ändert).
  - Pro Tab: Übersichts-Liste + „Neu“-Button + Dialog-Formulare zum
    Anlegen/Bearbeiten.
  - Im Artikel-Tab zusätzlich ein Rezept-Editor-Dialog, der die
    Standard-Zutaten verwaltet.

Designentscheidungen:
  - `ui.refreshable` für die drei Listen — nach jedem CRUD-Vorgang wird
    nur die betroffene Liste neu gerendert, nicht die ganze Seite.
  - Decimal-Eingabe via `ui.number`, beim Speichern aber zu `Decimal`
    konvertiert (über `str()`-Umweg, damit kein Float-Rundungsfehler
    in den Preis kommt).
  - Hier wird KEIN Login geprüft — das Auth-Gating wird im Router
    (`app.py`) bzw. von Irems `AuthService` übernommen, sobald es da
    ist. Diese Page geht davon aus, dass der Aufrufer Admin ist.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from nicegui import ui

from domain.models import Artikel, Kategorie, Zutat
from services.artikel_service import ArtikelService


# ---------------------------------------------------------------------------
# Page-Routing
# ---------------------------------------------------------------------------


@ui.page("/admin")
def admin_seite() -> None:
    """Einstiegspunkt für die Route `/admin`.

    Lädt alle drei Tabs auf einmal — die Daten innerhalb der Tabs werden
    aber lazy via `ui.refreshable` geholt, sodass das initiale Render
    schnell bleibt.
    """
    _kopfzeile()

    with ui.tabs().classes("w-full") as tabs:
        artikel_tab = ui.tab("Artikel", icon="restaurant_menu")
        kategorien_tab = ui.tab("Kategorien", icon="category")
        zutaten_tab = ui.tab("Zutaten", icon="eco")

    with ui.tab_panels(tabs, value=artikel_tab).classes("w-full"):
        with ui.tab_panel(artikel_tab):
            _artikel_panel()
        with ui.tab_panel(kategorien_tab):
            _kategorien_panel()
        with ui.tab_panel(zutaten_tab):
            _zutaten_panel()


def _kopfzeile() -> None:
    """Header der Admin-Seite."""
    with ui.row().classes("w-full items-center justify-between p-4"):
        ui.label("Pizzeria Sunshine — Admin").classes("text-2xl font-bold")
        ui.link("Zur Kunden-Ansicht", "/menu").classes("text-sm")


# ===========================================================================
# Tab 1: Artikel
# ===========================================================================


def _artikel_panel() -> None:
    """Layout des Artikel-Tabs: Action-Bar + refreshable Liste."""
    with ui.column().classes("w-full gap-3 p-4"):
        with ui.row().classes("w-full justify-end"):
            ui.button(
                "Neuer Artikel",
                icon="add",
                on_click=_artikel_anlegen_dialog,
            ).props("color=primary")
        _artikel_liste()


@ui.refreshable
def _artikel_liste() -> None:
    """Zeigt alle Artikel gruppiert nach Kategorie.

    Wir nutzen `menue_laden` mit `nur_verfuegbar=False` und
    `leere_kategorien_zeigen=True`, damit der Admin auch ausverkaufte
    Artikel und leere Kategorien sieht (sonst kann er die nicht
    bearbeiten).
    """
    menue = ArtikelService.menue_laden(
        nur_verfuegbar=False, leere_kategorien_zeigen=True
    )
    if not menue:
        ui.label(
            "Noch keine Kategorien angelegt. Bitte zuerst im Tab "
            "„Kategorien“ eine anlegen."
        ).classes("text-gray-600")
        return

    for eintrag in menue:
        # Expansion = aufklappbarer Block. Erste Kategorie offen,
        # damit man beim Reinkommen direkt etwas sieht.
        offen_per_default = eintrag is menue[0]
        with ui.expansion(
            f"{eintrag.kategorie.name} ({len(eintrag.artikel)})",
            icon="category",
            value=offen_per_default,
        ).classes("w-full"):
            if not eintrag.artikel:
                ui.label("Noch keine Artikel in dieser Kategorie.").classes(
                    "text-sm text-gray-500 px-4 py-2"
                )
            for artikel in eintrag.artikel:
                _artikel_zeile(artikel)


def _artikel_zeile(artikel: Artikel) -> None:
    """Eine einzelne Artikel-Zeile mit Inline-Aktionen."""
    with ui.row().classes("w-full items-center px-4 py-2 border-t"):
        ui.label(f"#{artikel.id}").classes("w-12 text-sm text-gray-500")
        ui.label(artikel.name).classes("flex-grow font-medium")
        ui.label(f"CHF {artikel.preis:.2f}").classes("w-24")
        ui.switch(
            value=artikel.verfuegbar,
            on_change=lambda _, a_id=artikel.id: _artikel_verfuegbarkeit_toggle(
                a_id
            ),
        ).tooltip("Verfügbarkeit umschalten")
        ui.button(
            icon="edit",
            on_click=lambda a=artikel: _artikel_bearbeiten_dialog(a),
        ).props("flat dense").tooltip("Bearbeiten")
        ui.button(
            icon="restaurant",
            on_click=lambda a=artikel: _rezept_editor_dialog(a),
        ).props("flat dense").tooltip("Standard-Rezept")
        ui.button(
            icon="delete",
            on_click=lambda a=artikel: _artikel_loeschen_bestaetigen(a),
        ).props("flat dense color=negative").tooltip("Löschen")


# --- Artikel: Aktionen --------------------------------------------------------


def _artikel_verfuegbarkeit_toggle(artikel_id: int) -> None:
    """Schaltet die Verfügbarkeit eines Artikels um (vom Switch ausgelöst)."""
    try:
        aktualisiert = ArtikelService.verfuegbarkeit_umschalten(artikel_id)
        zustand = "verfügbar" if aktualisiert.verfuegbar else "nicht verfügbar"
        ui.notify(
            f"„{aktualisiert.name}“ ist jetzt {zustand}.", type="positive"
        )
    except ValueError as exc:
        ui.notify(str(exc), type="negative")
        _artikel_liste.refresh()


def _artikel_loeschen_bestaetigen(artikel: Artikel) -> None:
    """Bestätigungs-Dialog für „Artikel löschen“."""
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Artikel „{artikel.name}“ wirklich löschen?").classes(
            "text-base"
        )
        ui.label(
            "Hinweis: Wenn der Artikel in bestehenden Bestellungen "
            "vorkommt, schlägt das Löschen fehl. Du kannst ihn "
            "stattdessen auf „nicht verfügbar“ stellen."
        ).classes("text-sm text-gray-600")
        with ui.row().classes("justify-end gap-2"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat")
            ui.button(
                "Löschen",
                on_click=lambda: _artikel_loeschen_ausfuehren(artikel, dialog),
            ).props("color=negative")
    dialog.open()


def _artikel_loeschen_ausfuehren(artikel: Artikel, dialog: ui.dialog) -> None:
    """Führt das Löschen aus und schliesst den Bestätigungsdialog."""
    try:
        if ArtikelService.artikel_loeschen(artikel.id or 0):
            ui.notify(f"„{artikel.name}“ gelöscht.", type="positive")
        else:
            ui.notify("Artikel war schon weg.", type="info")
        dialog.close()
        _artikel_liste.refresh()
    except Exception as exc:  # noqa: BLE001 — wir wollen jeden DB-Fehler hier sehen
        # Häufigster Fall: IntegrityError, weil der Artikel in
        # `bestellposition` referenziert ist.
        ui.notify(
            f"Konnte nicht gelöscht werden: {exc}. "
            f"Tipp: auf „nicht verfügbar“ stellen statt löschen.",
            type="negative",
            multi_line=True,
        )


# --- Artikel: Anlegen / Bearbeiten Dialog ------------------------------------


def _artikel_anlegen_dialog() -> None:
    """Öffnet den Dialog im Anlege-Modus."""
    _artikel_form_dialog(artikel=None)


def _artikel_bearbeiten_dialog(artikel: Artikel) -> None:
    """Öffnet den Dialog im Bearbeiten-Modus."""
    _artikel_form_dialog(artikel=artikel)


def _artikel_form_dialog(artikel: Optional[Artikel]) -> None:
    """Gemeinsamer Dialog für Anlegen und Bearbeiten von Artikeln.

    Bei `artikel is None` werden die Felder leer/Default-Werte vorbelegt;
    bei einem übergebenen Artikel die existierenden Werte. Der Submit-
    Handler wählt auf Basis derselben Bedingung Anlegen oder Bearbeiten
    im Service. So bleibt das Markup an einer Stelle.
    """
    titel = "Artikel bearbeiten" if artikel else "Neuer Artikel"

    kategorien = ArtikelService.kategorien_alle()
    if not kategorien:
        ui.notify(
            "Bitte zuerst eine Kategorie anlegen, bevor Artikel "
            "angelegt werden können.",
            type="warning",
        )
        return

    # Dropdown-Optionen: ID -> Name. NiceGUI mappt das automatisch.
    kategorien_options = {k.id: k.name for k in kategorien}
    default_kategorie = (
        artikel.kategorie_id if artikel else next(iter(kategorien_options))
    )

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
        ui.label(titel).classes("text-lg font-bold")

        name_input = ui.input(
            "Name", value=artikel.name if artikel else ""
        ).classes("w-full")
        kategorie_select = ui.select(
            options=kategorien_options,
            label="Kategorie",
            value=default_kategorie,
        ).classes("w-full")
        preis_input = ui.number(
            "Preis (CHF)",
            value=float(artikel.preis) if artikel else 0.0,
            format="%.2f",
            step=0.10,
            min=0,
        ).classes("w-full")
        beschreibung_input = ui.textarea(
            "Beschreibung",
            value=(artikel.beschreibung or "") if artikel else "",
        ).classes("w-full")
        bild_url_input = ui.input(
            "Bild-URL (optional)",
            value=(artikel.bild_url or "") if artikel else "",
        ).classes("w-full")
        verfuegbar_switch = ui.switch(
            "Verfügbar", value=artikel.verfuegbar if artikel else True
        )

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat")
            ui.button(
                "Speichern",
                on_click=lambda: _artikel_speichern(
                    artikel=artikel,
                    name_input=name_input,
                    kategorie_select=kategorie_select,
                    preis_input=preis_input,
                    beschreibung_input=beschreibung_input,
                    bild_url_input=bild_url_input,
                    verfuegbar_switch=verfuegbar_switch,
                    dialog=dialog,
                ),
            ).props("color=primary")

    dialog.open()


def _artikel_speichern(
    *,
    artikel: Optional[Artikel],
    name_input: ui.input,
    kategorie_select: ui.select,
    preis_input: ui.number,
    beschreibung_input: ui.textarea,
    bild_url_input: ui.input,
    verfuegbar_switch: ui.switch,
    dialog: ui.dialog,
) -> None:
    """Validiert die Form-Eingaben und ruft den Service.

    Liegt absichtlich ausserhalb des Dialogs, damit es testbar bleibt
    und der Dialog-Code nicht unter einer einzigen 80-Zeilen-Closure
    erstickt.
    """
    name = (name_input.value or "").strip()
    if not name:
        ui.notify("Name darf nicht leer sein.", type="negative")
        return

    # Decimal-Konvertierung über str(), damit der Float-Wert aus
    # `ui.number` keinen Rundungsfehler in den Preis schleppt.
    try:
        preis = Decimal(str(preis_input.value))
    except (InvalidOperation, TypeError):
        ui.notify("Preis ist ungültig.", type="negative")
        return

    beschreibung = (beschreibung_input.value or "").strip() or None
    bild_url = (bild_url_input.value or "").strip() or None
    kategorie_id = int(kategorie_select.value)

    try:
        if artikel is None:
            ergebnis = ArtikelService.artikel_anlegen(
                name=name,
                kategorie_id=kategorie_id,
                preis=preis,
                beschreibung=beschreibung,
                bild_url=bild_url,
                verfuegbar=verfuegbar_switch.value,
            )
        else:
            ergebnis = ArtikelService.artikel_bearbeiten(
                artikel.id or 0,
                name=name,
                kategorie_id=kategorie_id,
                preis=preis,
                beschreibung=beschreibung,
                bild_url=bild_url,
                verfuegbar=verfuegbar_switch.value,
            )
    except ValueError as exc:
        ui.notify(str(exc), type="negative")
        return

    # Soft-Warnungen vom Service nach oben durchreichen.
    for warnung in ergebnis.warnungen:
        ui.notify(warnung, type="warning", multi_line=True)

    ui.notify(f"„{ergebnis.artikel.name}“ gespeichert.", type="positive")
    dialog.close()
    _artikel_liste.refresh()


# --- Rezept-Editor -----------------------------------------------------------


def _rezept_editor_dialog(artikel: Artikel) -> None:
    """Dialog zum Bearbeiten des Standard-Rezepts eines Artikels.

    Workflow:
      1. Aktuelles Rezept laden (mit eager-loaded Zutat).
      2. State als Liste von Dicts halten (zutat_id, menge), damit
         wir Zeilen lokal hinzufügen/entfernen können, ohne pro
         Klick die DB anzufassen.
      3. „Speichern“ ruft `rezept_setzen` mit dem kompletten neuen
         Rezept auf — der Service löscht das alte atomar.
    """
    if artikel.id is None:
        ui.notify("Artikel hat keine ID — bitte zuerst speichern.", type="negative")
        return

    artikel_geladen, rezept = ArtikelService.artikel_mit_rezept_laden(
        artikel.id
    )
    alle_zutaten = ArtikelService.zutaten_alle()
    if not alle_zutaten:
        ui.notify(
            "Bitte zuerst Zutaten anlegen, bevor ein Rezept gebaut "
            "werden kann.",
            type="warning",
        )
        return

    # State-Liste — wird vom Render gelesen und von den Buttons mutiert.
    rezept_state: list[dict] = [
        {"zutat_id": eintrag.zutat_id, "menge": Decimal(eintrag.menge)}
        for eintrag in rezept
    ]
    zutaten_options = {z.id: z.name for z in alle_zutaten}

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
        ui.label(f"Rezept: {artikel_geladen.name}").classes(
            "text-lg font-bold"
        )

        liste_container = ui.column().classes("w-full gap-2")

        def zeilen_rendern() -> None:
            """Zeichnet die State-Liste neu in `liste_container`."""
            liste_container.clear()
            with liste_container:
                if not rezept_state:
                    ui.label("Noch keine Zutaten im Rezept.").classes(
                        "text-sm text-gray-500"
                    )
                for index, eintrag in enumerate(rezept_state):
                    _rezept_zeile(
                        index=index,
                        eintrag=eintrag,
                        zutaten_options=zutaten_options,
                        rezept_state=rezept_state,
                        zeilen_rendern=zeilen_rendern,
                    )

        zeilen_rendern()

        ui.button(
            "Zutat hinzufügen",
            icon="add",
            on_click=lambda: (
                rezept_state.append(
                    {
                        "zutat_id": next(iter(zutaten_options)),
                        "menge": Decimal("1"),
                    }
                ),
                zeilen_rendern(),
            ),
        ).props("flat")

        with ui.row().classes("w-full justify-end gap-2 mt-3"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat")
            ui.button(
                "Speichern",
                on_click=lambda: _rezept_speichern(
                    artikel_id=artikel.id or 0,
                    rezept_state=rezept_state,
                    dialog=dialog,
                ),
            ).props("color=primary")

    dialog.open()


def _rezept_zeile(
    *,
    index: int,
    eintrag: dict,
    zutaten_options: dict,
    rezept_state: list[dict],
    zeilen_rendern,
) -> None:
    """Eine einzelne Zeile im Rezept-Editor: Zutat-Dropdown + Menge + X."""
    with ui.row().classes("w-full items-center gap-2"):
        ui.select(
            options=zutaten_options,
            value=eintrag["zutat_id"],
            on_change=lambda e, idx=index: rezept_state[idx].update(
                {"zutat_id": int(e.value)}
            ),
        ).classes("flex-grow")
        ui.number(
            value=float(eintrag["menge"]),
            format="%.2f",
            step=0.5,
            min=0,
            on_change=lambda e, idx=index: rezept_state[idx].update(
                {"menge": Decimal(str(e.value or 0))}
            ),
        ).classes("w-24").tooltip("Menge")
        ui.button(
            icon="close",
            on_click=lambda idx=index: (rezept_state.pop(idx), zeilen_rendern()),
        ).props("flat dense color=negative")


def _rezept_speichern(
    *,
    artikel_id: int,
    rezept_state: list[dict],
    dialog: ui.dialog,
) -> None:
    """Validiert keine Duplikate und ruft `rezept_setzen`."""
    # Duplikat-Check: jede Zutat darf nur einmal im Rezept sein
    # (Composite Primary Key auf der Junction-Tabelle).
    zutat_ids = [int(e["zutat_id"]) for e in rezept_state]
    if len(zutat_ids) != len(set(zutat_ids)):
        ui.notify(
            "Eine Zutat darf nur einmal im Rezept stehen. Wenn du mehr "
            "willst, erhöhe die Menge.",
            type="negative",
            multi_line=True,
        )
        return

    zutaten = [(int(e["zutat_id"]), Decimal(e["menge"])) for e in rezept_state]
    try:
        ArtikelService.rezept_setzen(artikel_id, zutaten)
    except ValueError as exc:
        ui.notify(str(exc), type="negative")
        return

    ui.notify("Rezept gespeichert.", type="positive")
    dialog.close()


# ===========================================================================
# Tab 2: Kategorien
# ===========================================================================


def _kategorien_panel() -> None:
    """Layout des Kategorien-Tabs."""
    with ui.column().classes("w-full gap-3 p-4"):
        with ui.row().classes("w-full justify-end"):
            ui.button(
                "Neue Kategorie",
                icon="add",
                on_click=_kategorie_anlegen_dialog,
            ).props("color=primary")
        _kategorien_liste()


@ui.refreshable
def _kategorien_liste() -> None:
    """Tabellen-artige Auflistung aller Kategorien."""
    kategorien = ArtikelService.kategorien_alle()
    if not kategorien:
        ui.label("Noch keine Kategorien angelegt.").classes("text-gray-600")
        return
    with ui.column().classes("w-full gap-0 border rounded"):
        # Kopfzeile
        with ui.row().classes("w-full items-center px-4 py-2 bg-gray-100 font-medium"):
            ui.label("ID").classes("w-12")
            ui.label("Name").classes("flex-grow")
            ui.label("Sortierung").classes("w-24")
            ui.label("Aktionen").classes("w-32 text-right")
        for kategorie in kategorien:
            _kategorie_zeile(kategorie)


def _kategorie_zeile(kategorie: Kategorie) -> None:
    """Eine einzelne Kategorie-Zeile mit Aktionen."""
    with ui.row().classes("w-full items-center px-4 py-2 border-t"):
        ui.label(f"#{kategorie.id}").classes("w-12 text-sm text-gray-500")
        with ui.column().classes("flex-grow gap-0"):
            ui.label(kategorie.name).classes("font-medium")
            if kategorie.beschreibung:
                ui.label(kategorie.beschreibung).classes(
                    "text-xs text-gray-600"
                )
        ui.label(str(kategorie.sortierung)).classes("w-24")
        with ui.row().classes("w-32 justify-end gap-1"):
            ui.button(
                icon="edit",
                on_click=lambda k=kategorie: _kategorie_bearbeiten_dialog(k),
            ).props("flat dense").tooltip("Bearbeiten")
            ui.button(
                icon="delete",
                on_click=lambda k=kategorie: _kategorie_loeschen_bestaetigen(k),
            ).props("flat dense color=negative").tooltip("Löschen")


def _kategorie_anlegen_dialog() -> None:
    _kategorie_form_dialog(kategorie=None)


def _kategorie_bearbeiten_dialog(kategorie: Kategorie) -> None:
    _kategorie_form_dialog(kategorie=kategorie)


def _kategorie_form_dialog(kategorie: Optional[Kategorie]) -> None:
    """Gemeinsamer Dialog für Anlegen/Bearbeiten von Kategorien."""
    titel = "Kategorie bearbeiten" if kategorie else "Neue Kategorie"
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
        ui.label(titel).classes("text-lg font-bold")
        name_input = ui.input(
            "Name", value=kategorie.name if kategorie else ""
        ).classes("w-full")
        beschreibung_input = ui.textarea(
            "Beschreibung",
            value=(kategorie.beschreibung or "") if kategorie else "",
        ).classes("w-full")
        sortierung_input = ui.number(
            "Sortierung (kleine Zahl = oben)",
            value=kategorie.sortierung if kategorie else 0,
            step=1,
            min=0,
        ).classes("w-full")

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat")
            ui.button(
                "Speichern",
                on_click=lambda: _kategorie_speichern(
                    kategorie=kategorie,
                    name_input=name_input,
                    beschreibung_input=beschreibung_input,
                    sortierung_input=sortierung_input,
                    dialog=dialog,
                ),
            ).props("color=primary")
    dialog.open()


def _kategorie_speichern(
    *,
    kategorie: Optional[Kategorie],
    name_input: ui.input,
    beschreibung_input: ui.textarea,
    sortierung_input: ui.number,
    dialog: ui.dialog,
) -> None:
    """Validiert Form-Eingaben und ruft den Service."""
    name = (name_input.value or "").strip()
    if not name:
        ui.notify("Name darf nicht leer sein.", type="negative")
        return
    beschreibung = (beschreibung_input.value or "").strip() or None
    sortierung = int(sortierung_input.value or 0)

    try:
        if kategorie is None:
            ArtikelService.kategorie_anlegen(
                name=name, beschreibung=beschreibung, sortierung=sortierung
            )
        else:
            ArtikelService.kategorie_bearbeiten(
                kategorie.id or 0,
                name=name,
                beschreibung=beschreibung,
                sortierung=sortierung,
            )
    except ValueError as exc:
        ui.notify(str(exc), type="negative")
        return

    ui.notify(f"Kategorie „{name}“ gespeichert.", type="positive")
    dialog.close()
    _kategorien_liste.refresh()
    # Artikel-Liste auch refreshen, weil sie nach Kategorien gruppiert ist.
    _artikel_liste.refresh()


def _kategorie_loeschen_bestaetigen(kategorie: Kategorie) -> None:
    """Bestätigungs-Dialog mit Hinweis auf FK-Schutz."""
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Kategorie „{kategorie.name}“ wirklich löschen?").classes(
            "text-base"
        )
        ui.label(
            "Wenn noch Artikel in dieser Kategorie sind, schlägt das "
            "Löschen fehl. Du kannst die Artikel zuerst in eine andere "
            "Kategorie verschieben."
        ).classes("text-sm text-gray-600")
        with ui.row().classes("justify-end gap-2"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat")
            ui.button(
                "Löschen",
                on_click=lambda: _kategorie_loeschen_ausfuehren(
                    kategorie, dialog
                ),
            ).props("color=negative")
    dialog.open()


def _kategorie_loeschen_ausfuehren(
    kategorie: Kategorie, dialog: ui.dialog
) -> None:
    try:
        if ArtikelService.kategorie_loeschen(kategorie.id or 0):
            ui.notify(
                f"Kategorie „{kategorie.name}“ gelöscht.", type="positive"
            )
        else:
            ui.notify("Kategorie war schon weg.", type="info")
        dialog.close()
        _kategorien_liste.refresh()
        _artikel_liste.refresh()
    except Exception as exc:  # noqa: BLE001
        ui.notify(
            f"Konnte nicht gelöscht werden: {exc}",
            type="negative",
            multi_line=True,
        )


# ===========================================================================
# Tab 3: Zutaten
# ===========================================================================


def _zutaten_panel() -> None:
    """Layout des Zutaten-Tabs."""
    with ui.column().classes("w-full gap-3 p-4"):
        with ui.row().classes("w-full justify-end"):
            ui.button(
                "Neue Zutat", icon="add", on_click=_zutat_anlegen_dialog
            ).props("color=primary")
        _zutaten_liste()


@ui.refreshable
def _zutaten_liste() -> None:
    """Tabellen-artige Auflistung aller Zutaten."""
    zutaten = ArtikelService.zutaten_alle()
    if not zutaten:
        ui.label("Noch keine Zutaten angelegt.").classes("text-gray-600")
        return
    with ui.column().classes("w-full gap-0 border rounded"):
        with ui.row().classes("w-full items-center px-4 py-2 bg-gray-100 font-medium"):
            ui.label("ID").classes("w-12")
            ui.label("Name").classes("flex-grow")
            ui.label("Preis").classes("w-24")
            ui.label("Einheit").classes("w-24")
            ui.label("Veg.").classes("w-12 text-center")
            ui.label("Verfügbar").classes("w-24 text-center")
            ui.label("Aktionen").classes("w-32 text-right")
        for zutat in zutaten:
            _zutat_zeile(zutat)


def _zutat_zeile(zutat: Zutat) -> None:
    """Eine einzelne Zutat-Zeile mit Aktionen."""
    with ui.row().classes("w-full items-center px-4 py-2 border-t"):
        ui.label(f"#{zutat.id}").classes("w-12 text-sm text-gray-500")
        ui.label(zutat.name).classes("flex-grow font-medium")
        ui.label(f"CHF {zutat.preis_pro_einheit:.2f}").classes("w-24")
        ui.label(zutat.einheit).classes("w-24 text-sm")
        # Vegetarisch als Icon, kompakter als ein Switch.
        ui.icon(
            "check" if zutat.vegetarisch else "close",
            color="green" if zutat.vegetarisch else "grey",
        ).classes("w-12")
        with ui.row().classes("w-24 justify-center"):
            ui.switch(
                value=zutat.verfuegbar,
                on_change=lambda _, z_id=zutat.id: _zutat_verfuegbarkeit_toggle(
                    z_id
                ),
            )
        with ui.row().classes("w-32 justify-end gap-1"):
            ui.button(
                icon="edit",
                on_click=lambda z=zutat: _zutat_bearbeiten_dialog(z),
            ).props("flat dense").tooltip("Bearbeiten")
            ui.button(
                icon="delete",
                on_click=lambda z=zutat: _zutat_loeschen_bestaetigen(z),
            ).props("flat dense color=negative").tooltip("Löschen")


def _zutat_verfuegbarkeit_toggle(zutat_id: int) -> None:
    try:
        aktualisiert = ArtikelService.zutat_verfuegbarkeit_umschalten(zutat_id)
        zustand = (
            "verfügbar" if aktualisiert.verfuegbar else "nicht verfügbar"
        )
        ui.notify(
            f"„{aktualisiert.name}“ ist jetzt {zustand}.", type="positive"
        )
    except ValueError as exc:
        ui.notify(str(exc), type="negative")
        _zutaten_liste.refresh()


def _zutat_anlegen_dialog() -> None:
    _zutat_form_dialog(zutat=None)


def _zutat_bearbeiten_dialog(zutat: Zutat) -> None:
    _zutat_form_dialog(zutat=zutat)


def _zutat_form_dialog(zutat: Optional[Zutat]) -> None:
    """Gemeinsamer Dialog für Anlegen/Bearbeiten von Zutaten."""
    titel = "Zutat bearbeiten" if zutat else "Neue Zutat"
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
        ui.label(titel).classes("text-lg font-bold")
        name_input = ui.input(
            "Name", value=zutat.name if zutat else ""
        ).classes("w-full")
        preis_input = ui.number(
            "Preis pro Einheit (CHF)",
            value=float(zutat.preis_pro_einheit) if zutat else 0.0,
            format="%.2f",
            step=0.10,
            min=0,
        ).classes("w-full")
        einheit_input = ui.input(
            "Einheit", value=zutat.einheit if zutat else "Portion"
        ).classes("w-full")
        vegetarisch_switch = ui.switch(
            "Vegetarisch", value=zutat.vegetarisch if zutat else True
        )
        verfuegbar_switch = ui.switch(
            "Verfügbar", value=zutat.verfuegbar if zutat else True
        )

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat")
            ui.button(
                "Speichern",
                on_click=lambda: _zutat_speichern(
                    zutat=zutat,
                    name_input=name_input,
                    preis_input=preis_input,
                    einheit_input=einheit_input,
                    vegetarisch_switch=vegetarisch_switch,
                    verfuegbar_switch=verfuegbar_switch,
                    dialog=dialog,
                ),
            ).props("color=primary")
    dialog.open()


def _zutat_speichern(
    *,
    zutat: Optional[Zutat],
    name_input: ui.input,
    preis_input: ui.number,
    einheit_input: ui.input,
    vegetarisch_switch: ui.switch,
    verfuegbar_switch: ui.switch,
    dialog: ui.dialog,
) -> None:
    name = (name_input.value or "").strip()
    if not name:
        ui.notify("Name darf nicht leer sein.", type="negative")
        return
    try:
        preis = Decimal(str(preis_input.value))
    except (InvalidOperation, TypeError):
        ui.notify("Preis ist ungültig.", type="negative")
        return
    einheit = (einheit_input.value or "Portion").strip() or "Portion"

    try:
        if zutat is None:
            ArtikelService.zutat_anlegen(
                name=name,
                preis_pro_einheit=preis,
                einheit=einheit,
                vegetarisch=vegetarisch_switch.value,
                verfuegbar=verfuegbar_switch.value,
            )
        else:
            ArtikelService.zutat_bearbeiten(
                zutat.id or 0,
                name=name,
                preis_pro_einheit=preis,
                einheit=einheit,
                vegetarisch=vegetarisch_switch.value,
                verfuegbar=verfuegbar_switch.value,
            )
    except ValueError as exc:
        ui.notify(str(exc), type="negative")
        return

    ui.notify(f"„{name}“ gespeichert.", type="positive")
    dialog.close()
    _zutaten_liste.refresh()


def _zutat_loeschen_bestaetigen(zutat: Zutat) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Zutat „{zutat.name}“ wirklich löschen?").classes(
            "text-base"
        )
        ui.label(
            "Wenn die Zutat in einem Standard-Rezept oder in einer "
            "Wunschpizza-Bestellung benutzt wird, schlägt das Löschen "
            "fehl. Du kannst sie stattdessen auf „nicht verfügbar“ "
            "stellen."
        ).classes("text-sm text-gray-600")
        with ui.row().classes("justify-end gap-2"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat")
            ui.button(
                "Löschen",
                on_click=lambda: _zutat_loeschen_ausfuehren(zutat, dialog),
            ).props("color=negative")
    dialog.open()


def _zutat_loeschen_ausfuehren(zutat: Zutat, dialog: ui.dialog) -> None:
    try:
        if ArtikelService.zutat_loeschen(zutat.id or 0):
            ui.notify(f"Zutat „{zutat.name}“ gelöscht.", type="positive")
        else:
            ui.notify("Zutat war schon weg.", type="info")
        dialog.close()
        _zutaten_liste.refresh()
    except Exception as exc:  # noqa: BLE001
        ui.notify(
            f"Konnte nicht gelöscht werden: {exc}",
            type="negative",
            multi_line=True,
        )
