"""
Pizzeria Sunshine — Einstiegspunkt
===================================
Diese Datei ist der zentrale Startpunkt der App. Sie verdrahtet alle
Komponenten und startet den NiceGUI-Server.

Aufgaben:
  1. DB-Schema initialisieren (Tabellen anlegen, falls noch nicht da)
  2. Cross-Service-Hooks verdrahten (BestellService -> QuittungService)
  3. Alle Page-Module importieren, damit ihre @ui.page(...)-Routen
     bei NiceGUI registriert werden
  4. NiceGUI starten — mit storage_secret, damit app.storage.user
     funktioniert (wird vom AuthService fuer die Session-Verwaltung
     gebraucht)

Start:
    python app.py
"""

from __future__ import annotations

from nicegui import app, ui

# --- 1. DB-Schema initialisieren -------------------------------------------
# Wichtig: VOR den Page-Imports passieren, damit beim ersten Request
# die Tabellen schon existieren. init_db() macht create_all idempotent —
# bei existierender DB wird nichts veraendert.
from utils.db import init_db

init_db()


# --- 2. Cross-Service-Hooks verdrahten -------------------------------------
# BestellService kennt QuittungService bewusst nicht direkt (entkoppelt).
# Wir verbinden die beiden hier zentral: nach erfolgreicher Bestellung
# ruft BestellService den Hook auf, der die Quittung erzeugt.
#
# Signatur: Callable[[Session, int], str]
#   - QuittungService.quittung_erzeugen(session, bestellung_id) -> pdf_pfad
#
# Wenn der Hook hier nicht gesetzt wird, gehen Bestellungen zwar durch,
# es entsteht aber NIE eine PDF-Quittung. Stiller Bug — daher zentral hier.
from services.bestell_service import BestellService
from services.quittung_service import QuittungService

BestellService.quittung_hook = QuittungService.quittung_erzeugen


# --- 3. Page-Module importieren --------------------------------------------
# Jedes Page-Modul hat seine eigenen @ui.page(...)-Decorators. Sie werden
# erst aktiv, wenn das Modul importiert wurde — sonst kennt NiceGUI die
# Routen nicht. Importe sind absichtlich am Modul-Ende, NACH den Hooks
# und der DB-Init, damit alle Abhaengigkeiten bereit sind.
from pages import (  # noqa: F401 - Import nur fuer Side-Effects
    admin_page,
    bestellungen_page,
    checkout_page,
    login_page,
    menu_page,
    warenkorb_page,
)


# --- 4. Root-Route ---------------------------------------------------------
# Eine einfache Startseite, die je nach Login-Status weiterleitet.
# So muss niemand /login oder /menu manuell eintippen.
from services.auth_service import AuthService


@ui.page("/")
def startseite() -> None:
    """Leitet zum Menue (eingeloggt) oder zum Login (nicht eingeloggt)."""
    if AuthService.ist_eingeloggt():
        ui.navigate.to("/menu")
    else:
        ui.navigate.to("/login")


# --- 5. App starten --------------------------------------------------------
# storage_secret ist Pflicht fuer app.storage.user. Der String wird zum
# Signieren der Session-Cookies benutzt — in Produktion aus einer Env-Var,
# fuer das Schul-Projekt reicht ein langer Zufalls-String hier.
#
# port=8080 ist NiceGUI-Default; reload=False fuer stabilen Demo-Run.
# title erscheint im Browser-Tab.
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Pizzeria Sunshine",
        port=8080,
        reload=False,
        storage_secret="aendere_mich_vor_der_abgabe_xyz_pizzeria_sunshine_2026",
    )