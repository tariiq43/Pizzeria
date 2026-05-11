"""
Page — /checkout
=================
Checkout-Seite: Adresse wählen, Zahlungsmethode auswählen, bestellen.

Ablauf für den Kunden:
  1. Übersicht des Warenkorbs (read-only — Änderungen unter /warenkorb)
  2. Lieferadresse aus seinen gespeicherten Adressen wählen
  3. Zahlungsmethode wählen (gefakt — alles erfolgreich)
  4. Optional: Bemerkung dazuschreiben
  5. Button „Jetzt bezahlen“ -> ruft `BestellService.bestellung_aufgeben()`
  6. Bei Erfolg: Bestätigung mit Bestellnummer + Quittungs-Hinweis.

Login & Adressen:
  Wir brauchen einen Kunden mit mindestens einer Adresse. Solange Irems
  AuthService nicht da ist, nehmen wir den Demo-Kunden — analog zur
  Warenkorb-Page. Die Adressen ziehen wir über `AdresseDAO` (gehört zu
  Irem, aber wir lesen nur — kein Eingriff in ihren Code).
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from dao.adresse_dao import AdresseDAO
from services.bestell_service import BestellService, BestellErgebnis


# ---------------------------------------------------------------------------
# Login-Stub (gleicher Mechanismus wie in warenkorb_page.py)
# ---------------------------------------------------------------------------


_DEMO_KUNDEN_ID = 1


def _aktuelle_kunden_id() -> int:
    """Liefert die ID des eingeloggten Kunden (Demo-Fallback).

    Wird ersetzt, sobald Irems AuthService da ist — Stelle ist hier
    isoliert, damit der Tausch eine Ein-Zeilen-Änderung wird.
    """
    return _DEMO_KUNDEN_ID


# ---------------------------------------------------------------------------
# Modul-State für die Auswahl-Felder
# ---------------------------------------------------------------------------


# Wie im Warenkorb-Builder: Modul-Scope, damit Werte beim Re-Render
# erhalten bleiben.
_ausgewaehlte_adresse_id: Optional[int] = None
_ausgewaehlte_zahlungsmethode: str = "karte"
_bemerkung_text: str = ""


# ---------------------------------------------------------------------------
# Page-Routing
# ---------------------------------------------------------------------------


@ui.page("/checkout")
def checkout_seite() -> None:
    """Einstiegspunkt für `/checkout`."""
    _kopfzeile()

    # Warenkorb laden und validieren — leer oder unter Mindestbestellwert:
    # zurück zum Warenkorb schicken.
    inhalt = BestellService.warenkorb_lesen(_aktuelle_kunden_id())
    if not inhalt.items:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.label("Dein Warenkorb ist leer.").classes(
                "text-lg text-gray-600"
            )
            ui.button(
                "Zum Menü", on_click=lambda: ui.navigate.to("/menu")
            ).props("color=primary")
        return

    if not inhalt.mindestbestellwert_erreicht:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.label(
                f"Mindestbestellwert von CHF "
                f"{inhalt.mindestbestellwert:.2f} nicht erreicht."
            ).classes("text-lg text-red-600")
            ui.button(
                "Zurück zum Warenkorb",
                on_click=lambda: ui.navigate.to("/warenkorb"),
            ).props("color=primary")
        return

    _warenkorb_uebersicht(inhalt)
    ui.separator()
    _adressen_auswahl()
    ui.separator()
    _zahlungsmethode_auswahl()
    ui.separator()
    _bemerkung_feld()
    ui.separator()
    _bezahlen_block(inhalt.gesamtsumme)


# ---------------------------------------------------------------------------
# UI-Bausteine
# ---------------------------------------------------------------------------


def _kopfzeile() -> None:
    """Header — Titel und Link zurück zum Warenkorb."""
    with ui.row().classes("w-full items-center justify-between p-4"):
        ui.label("Checkout").classes("text-2xl font-bold")
        ui.button(
            "Zurück zum Warenkorb",
            on_click=lambda: ui.navigate.to("/warenkorb"),
        ).props("flat")


def _warenkorb_uebersicht(inhalt) -> None:
    """Read-only Übersicht des Warenkorbs.

    Bewusst kompakt: keine Mengen-Buttons hier. Wer ändern will, geht
    zurück zum Warenkorb.
    """
    with ui.column().classes("w-full p-4 gap-2"):
        ui.label("Deine Bestellung").classes("text-xl font-semibold")
        for item in inhalt.items:
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(f"{item.menge}× {item.artikel_name}").classes(
                    "text-base"
                )
                ui.label(f"CHF {item.positionssumme():.2f}").classes(
                    "text-base"
                )
        with ui.row().classes(
            "w-full items-center justify-between mt-2"
        ):
            ui.label("Gesamt").classes("text-lg font-bold")
            ui.label(f"CHF {inhalt.gesamtsumme:.2f}").classes(
                "text-lg font-bold"
            )


def _adressen_auswahl() -> None:
    """Dropdown der gespeicherten Adressen des Kunden."""
    with ui.column().classes("w-full p-4 gap-2"):
        ui.label("Lieferadresse").classes("text-xl font-semibold")

        adressen = AdresseDAO.alle_fuer_kunde(_aktuelle_kunden_id())
        if not adressen:
            ui.label(
                "Keine Adresse hinterlegt. Bitte zuerst über das Profil "
                "(Irens Bereich) eine Adresse anlegen."
            ).classes("text-sm text-red-600")
            return

        optionen = {a.id: a.als_text() for a in adressen}

        # Standard-Adresse oder erste als Default
        global _ausgewaehlte_adresse_id
        if (
            _ausgewaehlte_adresse_id is None
            or _ausgewaehlte_adresse_id not in optionen
        ):
            standard = next((a for a in adressen if a.ist_standard), None)
            _ausgewaehlte_adresse_id = (
                standard.id if standard else next(iter(optionen.keys()))
            )

        ui.select(
            options=optionen,
            value=_ausgewaehlte_adresse_id,
            label="Adresse auswählen",
            on_change=lambda e: _adresse_setzen(e.value),
        ).classes("w-full max-w-md")


def _adresse_setzen(neue_id: int) -> None:
    """Speichert die gewählte Adresse-ID im Modul-State."""
    global _ausgewaehlte_adresse_id
    _ausgewaehlte_adresse_id = neue_id


def _zahlungsmethode_auswahl() -> None:
    """Radio-Buttons für die Zahlungsmethode (alle gefakt)."""
    with ui.column().classes("w-full p-4 gap-2"):
        ui.label("Zahlungsmethode").classes("text-xl font-semibold")
        ui.label("(In dieser Demo-Version werden alle Zahlungen "
                 "automatisch als erfolgreich verbucht.)").classes(
            "text-xs text-gray-500"
        )
        ui.radio(
            options={
                "karte": "Kreditkarte",
                "twint": "TWINT",
                "rechnung": "Rechnung",
            },
            value=_ausgewaehlte_zahlungsmethode,
            on_change=lambda e: _zahlungsmethode_setzen(e.value),
        )


def _zahlungsmethode_setzen(neue: str) -> None:
    """Speichert die gewählte Methode im Modul-State."""
    global _ausgewaehlte_zahlungsmethode
    _ausgewaehlte_zahlungsmethode = neue


def _bemerkung_feld() -> None:
    """Textfeld für eine optionale Bemerkung an die Pizzeria."""
    with ui.column().classes("w-full p-4 gap-2"):
        ui.label("Bemerkung (optional)").classes("text-xl font-semibold")
        ui.textarea(
            label="z. B. Klingel ist defekt, bitte anrufen.",
            value=_bemerkung_text,
            on_change=lambda e: _bemerkung_setzen(e.value),
        ).classes("w-full max-w-md")


def _bemerkung_setzen(neuer_text: str) -> None:
    """Speichert die Bemerkung im Modul-State."""
    global _bemerkung_text
    _bemerkung_text = neuer_text


def _bezahlen_block(gesamtsumme) -> None:
    """Der grosse „Jetzt bezahlen“-Button + Status-Anzeige."""
    with ui.column().classes("w-full p-4 gap-2 items-center"):
        ui.button(
            f"Jetzt bezahlen (CHF {gesamtsumme:.2f})",
            on_click=_bestellen_klicken,
        ).props("color=primary size=lg")


# ---------------------------------------------------------------------------
# Aktionen
# ---------------------------------------------------------------------------


def _bestellen_klicken() -> None:
    """Klick auf „Jetzt bezahlen“ — ruft den Bestell-Service auf."""
    # global-Deklarationen müssen am Funktionsanfang stehen, weil Python
    # sonst beim Re-Bind unten meckert ("used prior to global declaration").
    global _bemerkung_text

    if _ausgewaehlte_adresse_id is None:
        ui.notify("Bitte eine Lieferadresse wählen.", type="warning")
        return

    try:
        ergebnis: BestellErgebnis = BestellService.bestellung_aufgeben(
            kunden_id=_aktuelle_kunden_id(),
            lieferadresse_id=_ausgewaehlte_adresse_id,
            zahlungsmethode=_ausgewaehlte_zahlungsmethode,
            bemerkung=_bemerkung_text if _bemerkung_text else None,
        )
    except ValueError as e:
        ui.notify(f"Bestellung fehlgeschlagen: {e}", type="negative")
        return
    except Exception as e:
        # Z. B. FK-Probleme, DB-Fehler etc. — wir wollen die App nicht
        # crashen lassen, sondern dem Kunden eine Meldung zeigen.
        ui.notify(
            f"Unerwarteter Fehler: {e}. Bitte erneut versuchen.",
            type="negative",
        )
        return

    # Bemerkung + Auswahl zurücksetzen für den nächsten Einkauf
    _bemerkung_text = ""

    # Bestätigung als Dialog. NiceGUI-Dialogs sind modal und einfach
    # zu bauen — kein eigenes Popup-Routing nötig.
    _bestaetigungs_dialog(ergebnis)


def _bestaetigungs_dialog(ergebnis: BestellErgebnis) -> None:
    """Zeigt einen Bestätigungs-Dialog nach erfolgreichem Bestellen."""
    with ui.dialog() as dialog, ui.card():
        ui.label("Vielen Dank für deine Bestellung!").classes(
            "text-xl font-bold"
        )
        ui.label(f"Bestellnummer: {ergebnis.bestellung_id}").classes(
            "text-base"
        )
        ui.label(f"Bezahlt: CHF {ergebnis.gesamtbetrag:.2f}").classes(
            "text-base"
        )
        if ergebnis.quittung_pfad:
            ui.label(f"Quittung: {ergebnis.quittung_pfad}").classes(
                "text-sm text-gray-600"
            )
        else:
            ui.label(
                "Die Quittung wird erzeugt, sobald der Quittungs-Service "
                "verfügbar ist."
            ).classes("text-sm text-gray-500 italic")

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button(
                "Zum Menü",
                on_click=lambda: (dialog.close(), ui.navigate.to("/menu")),
            ).props("flat")
            ui.button(
                "Meine Bestellungen",
                on_click=lambda: (
                    dialog.close(),
                    ui.navigate.to("/bestellungen"),
                ),
            ).props("color=primary")

    dialog.open()
