"""
Page — /bestellungen
=====================
Bestellhistorie für den eingeloggten Kunden.

Funktionen:
  - Liste aller bisherigen Bestellungen (neueste zuerst)
  - Pro Bestellung: Datum, Status, Gesamtbetrag, Lieferadresse
  - Ausklappbare Details mit allen Positionen (inkl. Wunschpizza-Zutaten
    und Bemerkungen)
  - Button „Quittung herunterladen" — öffnet das PDF, sofern eine
    Quittung existiert

Abgrenzung zu anderen Pages:
  - `/warenkorb` und `/checkout` sind Mohammeds Pages — die kümmern sich
    um das Erstellen neuer Bestellungen.
  - Diese Page ist read-only: Kein Mutieren von Bestellungen, keine
    Status-Wechsel, kein Stornieren. Das ist (a) was der Kunde im
    Frontend braucht, (b) sauber abgegrenzt von Admin-Funktionen.

Login-Pflicht:
  Bestellhistorie zeigt persönliche Daten — ohne Login kein Zugriff.
  Wir benutzen den Helper `kunden_id_oder_redirect()` aus
  `login_page.py`, der bei fehlendem Login auf `/login` umleitet.

Datenzugriff:
  - Liste: `KundenService.bestellhistorie()` (öffnet eigene Session,
    liefert die Bestellungen — ohne Positionen, weil die in der
    Übersicht nicht gebraucht werden).
  - Details (beim Aufklappen): `BestellungDAO.get_by_id_mit_positionen()`
    lädt für EINE Bestellung Positionen + Wunschzutaten + Adresse mit
    Eager-Loading. Bewusst nicht für alle Bestellungen vorab — das wäre
    bei vielen Bestellungen unnötiger DB-Traffic.
  - Quittungs-Lookup: `QuittungService.quittung_fuer_bestellung()`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from nicegui import ui

from dao.bestellung_dao import BestellungDAO
from domain.models import Bestellposition, Bestellung, BestellStatus
from pages.login_page import kunden_id_oder_redirect
from services.kunden_service import KundenService
from services.quittung_service import QuittungService
from utils.db import get_session


# ---------------------------------------------------------------------------
# Page-Routing
# ---------------------------------------------------------------------------


@ui.page("/bestellungen")
def bestellungen_seite() -> None:
    """Einstiegspunkt für `/bestellungen`.

    Aufbau:
      1. Login-Check (redirect bei fehlendem Login).
      2. Header mit Titel und Navigation.
      3. Liste der Bestellungen — entweder Leerzustand oder Cards.

    Wie Mohammeds Pages: Die Funktion wird bei jedem Page-Load neu
    aufgerufen, deshalb bauen wir die UI komplett von Hand auf. Für die
    Liste reicht ein einmaliger Render — anders als der Warenkorb gibt's
    hier keine Aktionen, die einen Teil-Refresh bräuchten.
    """
    kunden_id = kunden_id_oder_redirect()
    if kunden_id is None:
        # Redirect läuft schon im Browser — Page-Funktion ohne weiteren
        # Inhalt verlassen. `ui.navigate.to` ist asynchron, ein weiteres
        # Rendern hier würde die Page kurz „aufblitzen" lassen.
        return

    _kopfzeile()
    _bestellungen_liste(kunden_id)


# ---------------------------------------------------------------------------
# Kopf
# ---------------------------------------------------------------------------


def _kopfzeile() -> None:
    """Header — Titel und Links zurück zu Menü / Logout."""
    with ui.row().classes("w-full items-center justify-between p-4"):
        ui.label("Meine Bestellungen").classes("text-2xl font-bold")
        with ui.row().classes("gap-2"):
            ui.button(
                "Zum Menü", on_click=lambda: ui.navigate.to("/menu")
            ).props("flat")
            ui.button(
                "Abmelden", on_click=lambda: ui.navigate.to("/logout")
            ).props("flat color=negative")


# ---------------------------------------------------------------------------
# Bestellliste
# ---------------------------------------------------------------------------


def _bestellungen_liste(kunden_id: int) -> None:
    """Zeichnet die komplette Liste der Bestellungen.

    Bei leerer Historie zeigen wir einen freundlichen Leerzustand mit
    einem Button, der direkt zum Menü führt — damit der Kunde nicht in
    einer Sackgasse landet.
    """
    bestellungen = KundenService.bestellhistorie(kunden_id)

    if not bestellungen:
        with ui.column().classes("w-full items-center p-8 gap-4"):
            ui.label("Du hast noch keine Bestellung aufgegeben.").classes(
                "text-lg text-gray-600"
            )
            ui.button(
                "Jetzt bestellen",
                on_click=lambda: ui.navigate.to("/menu"),
            ).props("color=primary size=lg")
        return

    with ui.column().classes("w-full gap-3 p-4"):
        for bestellung in bestellungen:
            _bestellung_karte(bestellung)


def _bestellung_karte(bestellung: Bestellung) -> None:
    """Eine Karte für eine einzelne Bestellung.

    Kopfzeile: ID, Datum, Status, Betrag — immer sichtbar.
    Body: Positionen + Adresse + Quittungs-Button — nur beim Aufklappen
    sichtbar (`ui.expansion`).
    """
    # Defensive: Bestellung ohne ID kann's theoretisch nicht geben (die
    # kommt aus der DB), aber Pylance/Pyright kennt das nicht. Mit dem
    # Check rutschen wir an einer möglichen None-Falle vorbei und
    # vermeiden gleichzeitig Typ-Warnungen.
    if bestellung.id is None:
        return

    titel = (
        f"Bestellung #{bestellung.id} · "
        f"{bestellung.bestellzeit.strftime('%d.%m.%Y %H:%M')}"
    )

    with ui.card().classes("w-full"):
        # Kopfzeile mit ID, Datum, Status, Betrag
        with ui.row().classes("w-full items-center justify-between gap-4"):
            ui.label(titel).classes("text-base font-semibold")
            with ui.row().classes("items-center gap-3"):
                _status_badge(bestellung.status)
                ui.label(f"CHF {bestellung.gesamtbetrag:.2f}").classes(
                    "text-lg font-bold"
                )

        # Details — auf Wunsch aufklappbar. NiceGUI lädt den Inhalt der
        # Expansion bei Page-Render trotzdem schon vor; den Lazy-Load
        # machen wir hier per Helper, der bei Bedarf eine eigene Session
        # öffnet und Positionen + Adresse nachlädt.
        with ui.expansion("Details anzeigen", icon="receipt_long").classes(
            "w-full"
        ):
            _bestellung_details(bestellung.id)


def _status_badge(status: BestellStatus) -> None:
    """Zeigt den Status als farbiges Badge.

    Farb-Codierung soll auf den ersten Blick klar machen, wo eine
    Bestellung steht:
      - Grau:   OFFEN (eben aufgegeben, noch nicht angefasst)
      - Blau:   IN_BEARBEITUNG (Küche kocht)
      - Orange: UNTERWEGS (Fahrer ist los)
      - Grün:   GELIEFERT (alles erledigt)
      - Rot:    STORNIERT
    Falls Mohammed später noch einen Status ergänzt, fällt das auf den
    grauen Default zurück — kein UI-Crash.
    """
    farben = {
        BestellStatus.OFFEN: "grey",
        BestellStatus.IN_BEARBEITUNG: "blue",
        BestellStatus.UNTERWEGS: "orange",
        BestellStatus.GELIEFERT: "green",
        BestellStatus.STORNIERT: "red",
    }
    farbe = farben.get(status, "grey")
    ui.badge(status.value, color=farbe).props("outline")


# ---------------------------------------------------------------------------
# Bestelldetails (Lazy-Load bei Aufklappen)
# ---------------------------------------------------------------------------


def _bestellung_details(bestellung_id: int) -> None:
    """Lädt eine Bestellung mit allen Positionen und rendert die Details.

    Eigene DB-Session öffnen, damit die Lazy-Load-Relationen
    (`positionen`, `wunsch_zutaten`, `lieferadresse`) sauber gefüllt
    werden. Innerhalb des `with`-Blocks ist die Session noch offen, also
    können wir alle Attribute gefahrlos lesen — auch verschachtelte.
    """
    with get_session() as session:
        bestellung = BestellungDAO.get_by_id_mit_positionen(
            session, bestellung_id
        )
        if bestellung is None:
            ui.label("Bestellung konnte nicht geladen werden.").classes(
                "text-sm text-red-600"
            )
            return

        # Lieferadresse — optional. Falls die Adresse mal gelöscht wurde
        # (sollte wegen FK nicht passieren, aber schaden tut's nicht):
        # Fallback-Text statt UI-Crash.
        if bestellung.lieferadresse is not None:
            _adresse_block(bestellung.lieferadresse)
        else:
            ui.label("Lieferadresse nicht mehr verfügbar.").classes(
                "text-sm text-gray-500 italic"
            )

        # Positionen
        ui.separator()
        ui.label("Positionen").classes("text-base font-semibold mt-2")
        for position in bestellung.positionen:
            _position_zeile(position)

        # Quittung — nur Button anbieten, wenn das PDF auch wirklich da ist.
        ui.separator()
        _quittungs_block(bestellung_id)


def _adresse_block(adresse) -> None:
    """Rendert die Lieferadresse als kompakten Mehrzeiler."""
    with ui.column().classes("gap-0 mt-2"):
        ui.label("Lieferung an:").classes("text-sm font-semibold")
        ui.label(f"{adresse.strasse} {adresse.hausnummer}").classes(
            "text-sm"
        )
        ui.label(f"{adresse.plz} {adresse.ort}").classes("text-sm")


def _position_zeile(position: Bestellposition) -> None:
    """Eine Position-Zeile inkl. Wunschzutaten und Bemerkung."""
    # Name kommt vom verbundenen Artikel (eager-geladen)
    artikel_name = (
        position.artikel.name if position.artikel else "Unbekannter Artikel"
    )

    with ui.row().classes("w-full items-start justify-between gap-2 mt-1"):
        with ui.column().classes("flex-1 gap-0"):
            # Hauptzeile: Menge × Name
            ui.label(f"{position.menge} × {artikel_name}").classes(
                "text-sm"
            )

            # Wunschpizza-Zutaten (falls vorhanden)
            if position.wunsch_zutaten:
                zutaten = ", ".join(
                    wz.zutat.name
                    for wz in position.wunsch_zutaten
                    if wz.zutat is not None
                )
                if zutaten:
                    ui.label(f"+ {zutaten}").classes(
                        "text-xs text-gray-600 ml-4"
                    )

            # Bemerkung (z. B. „Bitte ohne Zwiebeln")
            if position.bemerkung:
                ui.label(f"„{position.bemerkung}\u201c").classes(
                    "text-xs text-gray-500 italic ml-4"
                )

        # Zeilen-Summe rechts
        ui.label(f"CHF {position.zeilen_summe():.2f}").classes(
            "text-sm font-semibold whitespace-nowrap"
        )


# ---------------------------------------------------------------------------
# Quittung
# ---------------------------------------------------------------------------


def _quittungs_block(bestellung_id: int) -> None:
    """Zeigt Quittungsnummer + Download-Button, sofern Quittung existiert.

    Theoretisch sollte nach einer erfolgreichen Bestellung IMMER eine
    Quittung da sein (Mohammeds Hook erzeugt sie atomar mit). In der
    Praxis kann der Hook aber fehlschlagen (z. B. PDF-Bibliothek
    abgestürzt) — in dem Fall steht die Bestellung trotzdem in der DB,
    nur die Quittung fehlt. Wir behandeln den Fall freundlich.
    """
    quittung = QuittungService.quittung_fuer_bestellung(bestellung_id)

    if quittung is None:
        ui.label("Quittung wird noch erstellt …").classes(
            "text-sm text-gray-500 italic mt-2"
        )
        return

    with ui.row().classes("w-full items-center justify-between mt-2"):
        ui.label(f"Quittung: {quittung.quittungsnummer}").classes(
            "text-sm font-semibold"
        )
        # Pfad-Existenz prüfen, BEVOR wir den Button anbieten — sonst
        # bekommt der Kunde einen 404 ins Gesicht.
        if quittung.pdf_pfad and Path(quittung.pdf_pfad).exists():
            ui.button(
                "Quittung herunterladen",
                icon="download",
                on_click=lambda pfad=quittung.pdf_pfad: _pdf_herunterladen(
                    pfad
                ),
            ).props("color=primary outline")
        else:
            ui.label("PDF nicht verfügbar").classes(
                "text-xs text-red-600"
            )


def _pdf_herunterladen(pdf_pfad: Optional[str]) -> None:
    """Triggert den Browser-Download für eine Quittung.

    `ui.download(...)` schickt die Datei als Attachment an den Browser —
    der Kunde bekommt den normalen Speicher-Dialog. Falls die Datei
    nicht mehr existiert (z. B. wurde sie zwischen Page-Render und Klick
    gelöscht), gibt's eine freundliche Notify-Meldung statt eines
    500ers.
    """
    if pdf_pfad is None or not Path(pdf_pfad).exists():
        ui.notify(
            "Quittungs-PDF konnte nicht gefunden werden.",
            type="negative",
        )
        return
    # `filename`-Argument bestimmt den vorgeschlagenen Speichernamen
    # beim Kunden — die interne Pfad-Struktur (`quittungen/...`) bleibt
    # so verborgen.
    ui.download(pdf_pfad, filename=Path(pdf_pfad).name)