"""
QuittungService — Pizzeria Sunshine
====================================
Erzeugt Quittungen nach erfolgreicher Bestellung — Quittungsnummer
generieren, PDF erzeugen, DB-Eintrag anlegen — und stellt Lese-Methoden
für die UI bereit.

Integration in den Bestell-Flow (Mohammeds Code):
    Mohammeds `BestellService` hat einen `quittung_hook`-Slot, der
    nach erfolgreicher Zahlung aufgerufen wird. In `app.py` (oder einer
    `main`-Initialisierung) wird der Hook einmalig gesetzt:

        from services.bestell_service import BestellService
        from services.quittung_service import QuittungService
        BestellService.quittung_hook = QuittungService.quittung_erzeugen

    `quittung_erzeugen` läuft dann INNERHALB von Mohammeds Transaktion
    mit der von ihm bereitgestellten Session. Damit sind Bestellung,
    Zahlung und Quittung atomar — entweder alles oder nichts.

Designentscheidungen:
  - **Hook-Methode bekommt `session` als Parameter** (keine eigene
    Session öffnen). Sonst würde die Quittung in einer separaten
    Transaktion laufen, und ein DB-Fehler beim Bestellen könnte trotzdem
    eine Quittung übrig lassen — oder umgekehrt eine Bestellung ohne
    Quittung.
  - **PDF wird VOR der DB-Mutation erzeugt.** Wenn die PDF-Erzeugung
    fehlschlägt, bleibt die DB sauber (keine Quittungs-Zeile ohne
    PDF). Erst wenn die Datei geschrieben ist, kommt die Zeile in die DB.
  - **Idempotent:** Existiert bereits eine Quittung für die Bestellung,
    geben wir deren Pfad zurück (oder erzeugen das PDF neu, falls die
    Datei verschwunden ist). So kann Mohammed seinen Hook bei einem
    Retry erneut aufrufen, ohne dass Duplikate entstehen.
  - **Quittungsnummer-Format `Q-YYYY-NNNNN`** (z. B. `Q-2026-00042`).
    Pro Jahr fortlaufend — kommt in der Schweizer Buchhaltung gut an
    und macht die Nummer sprechend ohne Datenschutz-Aspekt zu schwächen.
  - **Schweizer MwSt (reduzierter Satz 2.6 %)** für Speisen zum
    Mitnehmen / Lieferung (Stand 1.1.2024). Wäre die Pizza im Restaurant
    gegessen, wäre's der Normalsatz 8.1 % — ist hier aber egal, weil
    wir liefern. Falls sich das ändert, an EINER Stelle anpassen
    (`MWST_SATZ`).
  - **PDF-Layout delegiert an `utils.pdf_generator`.** Dieser Service
    kümmert sich nur um Geschäftslogik (Nummer, MwSt, Persistenz),
    nicht ums PDF-Layout. Bei Layout-Änderungen muss niemand hier
    rumfummeln.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from dao.bestellung_dao import BestellungDAO
from dao.quittung_dao import QuittungDAO
from domain.models import Quittung
from utils.db import get_session
from utils.pdf_generator import quittung_pdf_erzeugen


# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------


# Schweizer MwSt — reduzierter Satz für Speisen / Lieferung (Stand 1.1.2024).
# Wenn sich der Satz ändert, hier zentral anpassen — alle Berechnungen
# laufen über diese Konstante.
MWST_SATZ: Decimal = Decimal("0.026")  # 2.6 %


# Verzeichnis, in dem die Quittungs-PDFs landen. Wird beim ersten Aufruf
# angelegt, falls nicht vorhanden. Wer einen anderen Ablageort will
# (z. B. ein S3-Bucket oder ein anderes Verzeichnis), tauscht es hier.
QUITTUNGEN_VERZEICHNIS: Path = Path("quittungen")


# ---------------------------------------------------------------------------
# Wert-Objekt für die MwSt-Aufschlüsselung (auch fürs PDF-Layout)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MwStAufschluesselung:
    """Aufgeschlüsselter Betrag: brutto = netto + mwst.

    Auf Schweizer Quittungen ist die MwSt im Bruttobetrag enthalten.
    Wir rechnen den Netto- und MwSt-Anteil daher rückwärts aus dem
    Bruttobetrag (= dem Betrag, den der Kunde tatsächlich zahlt).

    `frozen=True` macht das Objekt unveränderbar — nach dem Erzeugen
    sind die Werte fix. So kann man es bedenkenlos durch mehrere
    Funktionen reichen, ohne dass jemand unterwegs etwas dran ändert.
    """

    brutto: Decimal
    netto: Decimal
    mwst: Decimal
    mwst_satz: Decimal  # z. B. Decimal("0.026")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class QuittungService:
    """Service zur Erzeugung und Verwaltung von Quittungen."""

    # Klassen-Konstante, damit Pages den Satz lesen können
    MWST_SATZ: Decimal = MWST_SATZ

    # =======================================================================
    # Hauptmethode — Hook für Mohammeds BestellService
    # =======================================================================

    @staticmethod
    def quittung_erzeugen(session: Session, bestellung_id: int) -> str:
        """Erzeugt eine Quittung für eine bezahlte Bestellung.

        Signatur passt genau auf `BestellService.quittung_hook`:
            Callable[[Session, int], str]

        Wird also innerhalb von Mohammeds Bestell-Transaktion aufgerufen.
        Wir benutzen die übergebene Session und öffnen KEINE eigene —
        sonst wäre die Quittung in einer separaten Transaktion und
        könnte unabhängig vom Rest committen.

        Ablauf:
          1. Bestellung laden (inkl. Positionen — für das PDF brauchen
             wir Artikel-Namen und Mengen).
          2. Existierende Quittung prüfen (Idempotenz). Wenn vorhanden
             und PDF existiert: deren Pfad zurückgeben.
          3. Quittungsnummer bestimmen (bestehende wiederverwenden oder
             neue generieren).
          4. PDF erzeugen (ZUERST, damit ein PDF-Fehler die DB nicht
             verschmutzt).
          5. Quittungs-Zeile anlegen oder updaten mit dem PDF-Pfad.
          6. Pfad zurückgeben.

        Rückgabe: absoluter Pfad zur erzeugten PDF (als String).

        Wirft `ValueError`, wenn die Bestellung nicht existiert.
        Wirft alle anderen Exceptions, die `quittung_pdf_erzeugen`
        wirft — Mohammed fängt sie und macht ohne PDF weiter (die
        Bestellung selbst bleibt gültig).
        """
        # 1. Bestellung laden — mit Positionen, weil das PDF die braucht
        bestellung = BestellungDAO.get_by_id_mit_positionen(
            session, bestellung_id
        )
        if bestellung is None:
            raise ValueError(
                f"Bestellung mit ID {bestellung_id} existiert nicht — "
                f"kann keine Quittung erzeugen."
            )

        # 2. Idempotenz — bestehende Quittung wiederverwenden
        bestehende = QuittungDAO.finde_per_bestellung(session, bestellung_id)
        if (
            bestehende is not None
            and bestehende.pdf_pfad
            and Path(bestehende.pdf_pfad).exists()
        ):
            # Es gibt schon Quittung + PDF — einfach Pfad zurück
            return bestehende.pdf_pfad

        # 3. Quittungsnummer bestimmen
        if bestehende is not None:
            # Halbe Quittung (Zeile da, aber PDF fehlt) — Nummer wiederverwenden
            nummer = bestehende.quittungsnummer
        else:
            nummer = QuittungService._naechste_quittungsnummer(
                session, datetime.now().year
            )

        # 4. PDF erzeugen — BEVOR wir die DB anfassen
        QUITTUNGEN_VERZEICHNIS.mkdir(parents=True, exist_ok=True)
        pdf_pfad = QUITTUNGEN_VERZEICHNIS / f"quittung_{nummer}.pdf"
        quittung_pdf_erzeugen(
            ziel_pfad=pdf_pfad,
            bestellung=bestellung,
            quittungsnummer=nummer,
            mwst=QuittungService.mwst_aufschluesseln(bestellung.gesamtbetrag),
        )
        pdf_pfad_str = str(pdf_pfad.resolve())

        # 5. DB-Zeile anlegen oder updaten
        if bestehende is None:
            quittung = Quittung(
                bestellung_id=bestellung_id,
                quittungsnummer=nummer,
                pdf_pfad=pdf_pfad_str,
            )
            QuittungDAO.create(session, quittung)
        else:
            bestehende.pdf_pfad = pdf_pfad_str
            QuittungDAO.update(session, bestehende)

        # 6. Pfad zurück an Mohammed
        return pdf_pfad_str

    # =======================================================================
    # Lese-Methoden für die UI (öffnen eigene Sessions)
    # =======================================================================

    @staticmethod
    def get_quittung(quittung_id: int) -> Optional[Quittung]:
        """Lädt eine Quittung über ihre Primary Key.

        Gibt `None` zurück, falls die ID nicht existiert.
        """
        with get_session() as session:
            return QuittungDAO.get_by_id(session, quittung_id)

    @staticmethod
    def quittung_fuer_bestellung(bestellung_id: int) -> Optional[Quittung]:
        """Liefert die Quittung zu einer Bestellung (oder None).

        Wird auf der `/bestellungen`-Seite verwendet: Der Kunde sieht
        seine Bestellung und klickt auf „Quittung herunterladen". Falls
        die Bestellung (warum auch immer) noch keine Quittung hat,
        kommt `None` — die UI zeigt dann z. B. „Quittung in Bearbeitung".
        """
        with get_session() as session:
            return QuittungDAO.finde_per_bestellung(session, bestellung_id)

    @staticmethod
    def quittung_per_nummer(quittungsnummer: str) -> Optional[Quittung]:
        """Findet eine Quittung anhand der Quittungsnummer.

        Praktisch für Support-Cases: Der Kunde nennt seine Nummer
        („Q-2026-00042"), der Mitarbeiter findet die Bestellung dazu.
        """
        with get_session() as session:
            return QuittungDAO.finde_per_quittungsnummer(
                session, quittungsnummer
            )

    @staticmethod
    def alle_quittungen_fuer_kunde(kunden_id: int) -> list[Quittung]:
        """Liefert alle Quittungen eines Kunden (neueste zuerst).

        Geht über den JOIN in `QuittungDAO.alle_fuer_kunde` — `Quittung`
        kennt den Kunden nur indirekt über `Bestellung`.
        """
        with get_session() as session:
            return QuittungDAO.alle_fuer_kunde(session, kunden_id)

    # =======================================================================
    # MwSt-Aufschlüsselung (utility — auch von der UI direkt nutzbar)
    # =======================================================================

    @staticmethod
    def mwst_aufschluesseln(brutto: Decimal) -> MwStAufschluesselung:
        """Rechnet aus einem Bruttobetrag den Netto- und MwSt-Anteil.

        Formel (MwSt ist im Bruttobetrag enthalten):
            netto = brutto / (1 + mwst_satz)
            mwst  = brutto - netto

        Beispiel: Bei 100.00 CHF brutto und 2.6 % MwSt:
            netto = 100 / 1.026 ≈ 97.47
            mwst  =   2.53

        Gerundet wird kaufmännisch auf 2 Nachkommastellen
        (ROUND_HALF_UP — 0.5 wird aufgerundet). Das ist die in der
        Schweizer Praxis übliche Rundung für Beträge in CHF.

        Wir nutzen `Decimal` statt `float`, damit es keine
        Rundungsfehler à la `0.1 + 0.2 == 0.30000000000000004` gibt —
        bei Geldbeträgen wäre das nicht akzeptabel.
        """
        brutto = brutto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        netto = (brutto / (Decimal("1") + MWST_SATZ)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        mwst = (brutto - netto).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return MwStAufschluesselung(
            brutto=brutto,
            netto=netto,
            mwst=mwst,
            mwst_satz=MWST_SATZ,
        )

    # =======================================================================
    # Interne Helfer
    # =======================================================================

    @staticmethod
    def _naechste_quittungsnummer(session: Session, jahr: int) -> str:
        """Erzeugt die nächste Quittungsnummer für ein Jahr.

        Format: `Q-{jahr}-{laufnummer:05d}`, z. B. `Q-2026-00042`.

        Strategie: Wir suchen die höchste bisherige Laufnummer für das
        Jahr und addieren 1. Wenn noch keine existiert, fangen wir bei
        00001 an.

        Edge-Case: Bei parallelen Schreibern könnten theoretisch zwei
        Bestellungen gleichzeitig dieselbe Nummer generieren. Weil
        `quittungsnummer` UNIQUE ist, würde die DB den Doppel-Insert
        ablehnen — bei SQLite + Schul-App reicht das aus. In einer
        echten Produktion mit hoher Last würde man einen Sequence-
        Counter in einer eigenen Tabelle nutzen.
        """
        praefix = f"Q-{jahr}-"
        # Alle Quittungsnummern dieses Jahres aus der DB ziehen
        statement = select(Quittung.quittungsnummer).where(
            Quittung.quittungsnummer.like(f"{praefix}%")
        )
        nummern = list(session.exec(statement).all())

        max_laufnummer = 0
        muster = re.compile(rf"^{re.escape(praefix)}(\d+)$")
        for n in nummern:
            treffer = muster.match(n)
            if treffer:
                laufnummer = int(treffer.group(1))
                if laufnummer > max_laufnummer:
                    max_laufnummer = laufnummer

        return f"{praefix}{max_laufnummer + 1:05d}"