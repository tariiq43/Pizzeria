"""
Page — /login & /logout
========================
Login und Registrierung — die zentrale Einstiegsseite für alle, die noch
nicht eingeloggt sind.

Aufbau:
  - Tab „Anmelden"      : Email + Passwort + Toggle Kunde / Mitarbeiter
  - Tab „Neu registrieren": Felder für die Kundenregistrierung
                            (Mitarbeiter werden nicht selbst registriert,
                             die legt der Admin an)

Nach erfolgreichem Login:
  - Kunde       → `/menu` (Bestellfrontend)
  - Mitarbeiter → `/menu` als Fallback (Admin-Bereich kommt später)

Die Methode `AuthService.session_setzen_kunde()` /
`session_setzen_mitarbeiter()` speichert den eingeloggten Nutzer in
`app.storage.user`. Andere Pages (Warenkorb, Checkout, Bestellhistorie)
lesen das über `AuthService.aktuelle_kunden_id()`.

Stil-Anmerkungen (passend zu Mohammeds Warenkorb/Checkout-Pages):
  - Modul-State für Formularwerte, damit die Werte bei einem Re-Render
    nicht verloren gehen.
  - `ui.notify()` für Erfolgs- und Fehlermeldungen.
  - `ui.navigate.to()` für Page-Übergänge.
  - Helper-Funktionen pro Sektion, damit der `@ui.page`-Einstieg lesbar
    bleibt.
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from services.auth_service import AuthService


# ---------------------------------------------------------------------------
# Modul-State — Formularwerte
# ---------------------------------------------------------------------------
#
# Bewusst Modul-Scope (nicht Closure innerhalb der Page-Funktion), damit
# eingegebene Werte beim partiellen Re-Render erhalten bleiben. NiceGUI
# baut die `@ui.page`-Funktion bei jedem Reload neu auf — Closure-State
# wäre dabei weg.


# Login-Formular
_login_email: str = ""
_login_passwort: str = ""
_login_typ: str = "kunde"  # "kunde" oder "mitarbeiter"

# Registrierungs-Formular
_reg_vorname: str = ""
_reg_nachname: str = ""
_reg_email: str = ""
_reg_passwort: str = ""
_reg_passwort_wiederholung: str = ""
_reg_telefon: str = ""


# ---------------------------------------------------------------------------
# Routing — /login
# ---------------------------------------------------------------------------


@ui.page("/login")
def login_seite() -> None:
    """Einstiegspunkt für `/login`.

    Wer schon eingeloggt ist, wird direkt aufs Menü geschickt — sonst
    sieht ein Kunde nach dem Reload die Login-Seite nochmal und ist
    irritiert.
    """
    if AuthService.ist_eingeloggt():
        ui.navigate.to("/menu")
        return

    _kopfzeile()

    with ui.column().classes("w-full items-center p-4 gap-4"):
        with ui.card().classes("w-full max-w-md"):
            with ui.tabs().classes("w-full") as tabs:
                anmelden_tab = ui.tab("Anmelden")
                registrieren_tab = ui.tab("Neu registrieren")

            with ui.tab_panels(tabs, value=anmelden_tab).classes("w-full"):
                with ui.tab_panel(anmelden_tab):
                    _login_formular()
                with ui.tab_panel(registrieren_tab):
                    _registrieren_formular()


# ---------------------------------------------------------------------------
# Kopf
# ---------------------------------------------------------------------------


def _kopfzeile() -> None:
    """Header — Branding und Link zurück zum Menü (für Besucher)."""
    with ui.row().classes("w-full items-center justify-between p-4"):
        ui.label("Pizzeria Sunshine").classes("text-2xl font-bold")
        ui.button(
            "Zum Menü (ohne Anmelden)",
            on_click=lambda: ui.navigate.to("/menu"),
        ).props("flat")


# ---------------------------------------------------------------------------
# Login-Formular
# ---------------------------------------------------------------------------


def _login_formular() -> None:
    """UI-Block für die Anmeldung.

    Radio-Buttons oben für die Auswahl Kunde / Mitarbeiter, danach die
    klassischen Felder Email + Passwort. Ein einziger Button schickt
    das Formular ab — die Logik im Callback verzweigt anhand von
    `_login_typ`.
    """
    with ui.column().classes("w-full gap-3 p-2"):
        ui.label("Bitte melde dich an").classes("text-lg font-semibold")

        # Kunde / Mitarbeiter
        ui.radio(
            options={"kunde": "Kunde", "mitarbeiter": "Mitarbeiter"},
            value=_login_typ,
            on_change=lambda e: _login_typ_setzen(e.value),
        ).props("inline")

        # Email
        ui.input(
            label="Email",
            value=_login_email,
            on_change=lambda e: _login_email_setzen(e.value),
        ).classes("w-full").props("type=email")

        # Passwort
        ui.input(
            label="Passwort",
            value=_login_passwort,
            password=True,
            password_toggle_button=True,
            on_change=lambda e: _login_passwort_setzen(e.value),
        ).classes("w-full")

        ui.button(
            "Anmelden", on_click=_anmelden_klicken
        ).props("color=primary size=lg").classes("w-full")


# Callbacks für die Login-Eingabefelder
def _login_email_setzen(neu: str) -> None:
    global _login_email
    _login_email = neu


def _login_passwort_setzen(neu: str) -> None:
    global _login_passwort
    _login_passwort = neu


def _login_typ_setzen(neu: str) -> None:
    global _login_typ
    _login_typ = neu


def _anmelden_klicken() -> None:
    """Klick auf „Anmelden" — verzweigt Kunde / Mitarbeiter."""
    # Basis-Validierung in der UI — der Service prüft das auch nochmal,
    # aber so sparen wir den Round-Trip.
    if not _login_email.strip() or not _login_passwort:
        ui.notify("Bitte Email und Passwort eingeben.", type="warning")
        return

    if _login_typ == "kunde":
        _login_als_kunde()
    elif _login_typ == "mitarbeiter":
        _login_als_mitarbeiter()
    else:
        # Defensive — sollte nicht passieren, weil nur Radio-Optionen
        ui.notify("Unbekannter Anmelde-Typ.", type="negative")


def _login_als_kunde() -> None:
    """Login-Pfad für Kunden."""
    global _login_email, _login_passwort

    kunde = AuthService.login_kunde(_login_email, _login_passwort)
    if kunde is None:
        # Bewusst KEINE Unterscheidung zwischen „Email falsch" und
        # „Passwort falsch" (siehe Modul-Docstring AuthService).
        ui.notify("Email oder Passwort falsch.", type="negative")
        return

    AuthService.session_setzen_kunde(kunde)
    # Formular zurücksetzen, damit nichts hängen bleibt
    _login_email = ""
    _login_passwort = ""

    ui.notify(
        f"Willkommen, {kunde.vorname}!", type="positive", position="top"
    )
    ui.navigate.to("/menu")


def _login_als_mitarbeiter() -> None:
    """Login-Pfad für Mitarbeiter."""
    global _login_email, _login_passwort

    mitarbeiter = AuthService.login_mitarbeiter(_login_email, _login_passwort)
    if mitarbeiter is None:
        # Selbe vage Meldung wie beim Kunden — Angreifer sollen nicht
        # erkennen, ob die Email überhaupt im System ist oder ob das
        # Konto aktiv ist.
        ui.notify("Email oder Passwort falsch.", type="negative")
        return

    AuthService.session_setzen_mitarbeiter(mitarbeiter)
    _login_email = ""
    _login_passwort = ""

    ui.notify(
        f"Willkommen, {mitarbeiter.vorname}!",
        type="positive",
        position="top",
    )
    # Admin-Bereich existiert noch nicht — vorerst aufs Menü.
    # Sobald Younus/Mohammed eine Admin-Page haben, hier umstellen.
    ui.navigate.to("/menu")


# ---------------------------------------------------------------------------
# Registrierungs-Formular (nur für Kunden)
# ---------------------------------------------------------------------------


def _registrieren_formular() -> None:
    """UI-Block für die Neuregistrierung eines Kunden.

    Mitarbeiter können sich NICHT selbst registrieren — die legt der
    Admin an. Das ist nicht nur UX, sondern auch ein Sicherheitsaspekt:
    Sonst könnte sich jeder selbst zum Mitarbeiter machen.
    """
    with ui.column().classes("w-full gap-3 p-2"):
        ui.label("Neues Kundenkonto anlegen").classes(
            "text-lg font-semibold"
        )
        ui.label(
            "Mitarbeiter-Konten werden vom Admin angelegt — bitte dort melden."
        ).classes("text-xs text-gray-500")

        with ui.row().classes("w-full gap-2"):
            ui.input(
                label="Vorname",
                value=_reg_vorname,
                on_change=lambda e: _reg_vorname_setzen(e.value),
            ).classes("flex-1")
            ui.input(
                label="Nachname",
                value=_reg_nachname,
                on_change=lambda e: _reg_nachname_setzen(e.value),
            ).classes("flex-1")

        ui.input(
            label="Email",
            value=_reg_email,
            on_change=lambda e: _reg_email_setzen(e.value),
        ).classes("w-full").props("type=email")

        ui.input(
            label="Telefon (optional)",
            value=_reg_telefon,
            on_change=lambda e: _reg_telefon_setzen(e.value),
        ).classes("w-full").props("type=tel")

        ui.input(
            label="Passwort",
            value=_reg_passwort,
            password=True,
            password_toggle_button=True,
            on_change=lambda e: _reg_passwort_setzen(e.value),
        ).classes("w-full")

        ui.input(
            label="Passwort wiederholen",
            value=_reg_passwort_wiederholung,
            password=True,
            on_change=lambda e: _reg_passwort_wdh_setzen(e.value),
        ).classes("w-full")

        ui.button(
            "Konto anlegen", on_click=_registrieren_klicken
        ).props("color=primary size=lg").classes("w-full")


# Callbacks für die Registrierungs-Eingabefelder
def _reg_vorname_setzen(neu: str) -> None:
    global _reg_vorname
    _reg_vorname = neu


def _reg_nachname_setzen(neu: str) -> None:
    global _reg_nachname
    _reg_nachname = neu


def _reg_email_setzen(neu: str) -> None:
    global _reg_email
    _reg_email = neu


def _reg_passwort_setzen(neu: str) -> None:
    global _reg_passwort
    _reg_passwort = neu


def _reg_passwort_wdh_setzen(neu: str) -> None:
    global _reg_passwort_wiederholung
    _reg_passwort_wiederholung = neu


def _reg_telefon_setzen(neu: str) -> None:
    global _reg_telefon
    _reg_telefon = neu


def _registrieren_klicken() -> None:
    """Klick auf „Konto anlegen" — Validierung + AuthService.

    UI-Validierung deckt nur das Offensichtliche ab (leere Felder,
    Passwörter stimmen überein). Die fachliche Validierung
    (Email schon vergeben, Passwort-Format) macht der `AuthService`
    und wirft `ValueError` — den fangen wir ab und zeigen die
    Nachricht direkt an.
    """
    global _reg_vorname, _reg_nachname, _reg_email
    global _reg_passwort, _reg_passwort_wiederholung, _reg_telefon

    # UI-Validierung
    if not _reg_vorname.strip():
        ui.notify("Vorname fehlt.", type="warning")
        return
    if not _reg_nachname.strip():
        ui.notify("Nachname fehlt.", type="warning")
        return
    if not _reg_email.strip():
        ui.notify("Email fehlt.", type="warning")
        return
    if not _reg_passwort:
        ui.notify("Passwort fehlt.", type="warning")
        return
    if _reg_passwort != _reg_passwort_wiederholung:
        ui.notify("Die Passwörter stimmen nicht überein.", type="warning")
        return
    if len(_reg_passwort) < 6:
        # Wir verbieten leere Passwörter im Service — hier setzen wir
        # zusätzlich eine UI-Mindestlänge, damit niemand „123" wählt.
        # Keine harte technische Grenze, nur eine Empfehlung.
        ui.notify(
            "Bitte ein Passwort mit mindestens 6 Zeichen wählen.",
            type="warning",
        )
        return

    try:
        kunde = AuthService.registriere_kunde(
            vorname=_reg_vorname,
            nachname=_reg_nachname,
            email=_reg_email,
            passwort=_reg_passwort,
            telefon=_reg_telefon if _reg_telefon.strip() else None,
        )
    except ValueError as e:
        # Z. B. „Email bereits registriert" — schön anzeigen.
        ui.notify(str(e), type="negative")
        return
    except Exception as e:
        ui.notify(
            f"Unerwarteter Fehler: {e}. Bitte erneut versuchen.",
            type="negative",
        )
        return

    # Erfolg — direkt einloggen, damit der Kunde nicht nochmal tippen muss
    AuthService.session_setzen_kunde(kunde)

    # Formular leeren
    _reg_vorname = ""
    _reg_nachname = ""
    _reg_email = ""
    _reg_passwort = ""
    _reg_passwort_wiederholung = ""
    _reg_telefon = ""

    ui.notify(
        f"Konto angelegt — willkommen, {kunde.vorname}!",
        type="positive",
        position="top",
    )
    ui.navigate.to("/menu")


# ---------------------------------------------------------------------------
# Routing — /logout
# ---------------------------------------------------------------------------


@ui.page("/logout")
def logout_seite() -> None:
    """Loggt den aktuellen Nutzer aus und leitet zurück zum Login.

    Eigene Page (nicht nur ein Button), damit man auch von ausserhalb
    einen sauberen Logout-Link einbauen kann (z. B. ein Email-Link
    nach Passwort-Reset, oder die Browser-Bookmarks).
    """
    AuthService.ausloggen()
    ui.notify("Du wurdest abgemeldet.", type="info")
    ui.navigate.to("/login")


# ---------------------------------------------------------------------------
# Helper für andere Pages — „Auth-Wand" um geschützte Bereiche legen
# ---------------------------------------------------------------------------


def kunden_id_oder_redirect() -> Optional[int]:
    """Liefert die eingeloggte Kunden-ID oder leitet auf /login um.

    Praktischer Helper für Pages, die zwingend einen eingeloggten
    Kunden brauchen (Warenkorb, Checkout, Bestellhistorie):

        kunden_id = kunden_id_oder_redirect()
        if kunden_id is None:
            return  # Page kann normal weiter — Redirect läuft im Browser

    Gibt `None` zurück, wenn kein Kunde eingeloggt ist — der Aufrufer
    sollte dann mit `return` raus, weil `ui.navigate.to` asynchron ist
    und die Page sonst weiter rendert.
    """
    kunden_id = AuthService.aktuelle_kunden_id()
    if kunden_id is None:
        ui.notify(
            "Bitte zuerst anmelden.", type="info", position="top"
        )
        ui.navigate.to("/login")
        return None
    return kunden_id