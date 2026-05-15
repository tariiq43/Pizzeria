"""
PDF-Generator für Quittungen — Pizzeria Sunshine
=================================================
Erzeugt eine PDF-Quittung über `reportlab`.

Wird vom `QuittungService` aufgerufen. Dieser Service liefert alle
nötigen Daten — die `bestellung` mit eager-loaded Positionen, die
Quittungsnummer und die MwSt-Aufschlüsselung. Diese Datei kümmert
sich ausschliesslich um das Layout der PDF.

Designentscheidungen:
  - **reportlab Platypus** (high-level API mit `SimpleDocTemplate` +
    Flowables wie `Paragraph`, `Table`, `Spacer`). Spart uns das
    manuelle Koordinaten-Frickeln mit dem rohen Canvas und macht das
    Layout responsiver (Tabellen brechen automatisch um, wenn der
    Inhalt wächst).
  - **Schweizer Konvention** — Beträge in CHF, Datum als
    `dd.MM.YYYY HH:mm`, deutsche Sprache. Die Pizzeria ist in der
    Schweiz — eine englische Quittung wäre seltsam.
  - **Trennung Geschäftslogik / Layout:** Diese Datei berechnet
    NICHTS. Sie bekommt fertige Werte vom Service und zeichnet sie.
    Wenn sich das Layout ändert, muss niemand im `QuittungService`
    rumfummeln. Wenn sich die MwSt-Berechnung ändert, muss niemand
    hier ran.
  - **Adresse der Pizzeria hart codiert** (siehe `_PIZZERIA_*`). Im
    Schul-Projekt ok — in einer echten App käme das aus einer
    Konfiguration oder einer DB-Tabelle „Filialen".

Abhängigkeit: `reportlab` muss installiert sein:
    pip install reportlab
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Nur fürs Type-Checking — vermeidet Zirkular-Imports zur Laufzeit.
if TYPE_CHECKING:
    from domain.models import Bestellung
    from services.quittung_service import MwStAufschluesselung


# ---------------------------------------------------------------------------
# Stammdaten der Pizzeria (hart codiert — siehe Modul-Docstring)
# ---------------------------------------------------------------------------


_PIZZERIA_NAME = "Pizzeria Sunshine"
_PIZZERIA_STRASSE = "Musterstrasse 1"
_PIZZERIA_PLZ_ORT = "4000 Basel"
_PIZZERIA_TELEFON = "+41 61 123 45 67"
_PIZZERIA_WEB = "www.pizzeria-sunshine.ch"


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------


def quittung_pdf_erzeugen(
    *,
    ziel_pfad: Path,
    bestellung: "Bestellung",
    quittungsnummer: str,
    mwst: "MwStAufschluesselung",
) -> None:
    """Schreibt eine PDF-Quittung an `ziel_pfad`.

    Erwartet, dass die Bestellung mit eager-loaded Positionen geladen
    wurde (siehe `BestellungDAO.get_by_id_mit_positionen`) — diese
    Funktion liest Felder wie `bestellung.positionen[i].artikel.name`,
    ohne sich um Lazy-Loading zu kümmern.

    Keyword-only-Argumente, damit am Aufruf-Ort sofort klar ist, was
    wo hingehört — vier Strings/Objekte ohne Keyword wären verwechslungs-
    anfällig.

    Wirft `OSError` etc., wenn das Schreiben fehlschlägt. Der Aufrufer
    (`QuittungService.quittung_erzeugen`) lässt die Exception bewusst
    durch — Mohammed fängt sie auf der nächsthöheren Ebene.
    """
    # SimpleDocTemplate erzeugt automatisch die PDF-Datei am Ziel-Pfad
    doc = SimpleDocTemplate(
        str(ziel_pfad),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Quittung {quittungsnummer}",
        author=_PIZZERIA_NAME,
    )

    story: list = []

    _kopfzeile(story)
    _trennlinie(story)
    _titel_und_meta(story, bestellung, quittungsnummer)
    _kunde_und_adresse(story, bestellung)
    _trennlinie(story)
    _positionen_tabelle(story, bestellung)
    _trennlinie(story)
    _summen_tabelle(story, mwst)
    _fusszeile(story)

    doc.build(story)


# ---------------------------------------------------------------------------
# Layout-Bausteine
# ---------------------------------------------------------------------------


def _styles() -> dict[str, ParagraphStyle]:
    """Bündelt die Absatz-Styles, damit sie nicht überall neu erzeugt werden.

    Eigene Funktion (statt Modul-Konstanten), weil reportlab
    `getSampleStyleSheet()` Stateful-Objekte zurückgibt und sich
    schlecht für Multi-Threading eignet — pro Aufruf frische Styles
    sind unkritisch und vermeiden Überraschungen.
    """
    base = getSampleStyleSheet()
    return {
        "firma": ParagraphStyle(
            "firma",
            parent=base["Heading1"],
            fontSize=18,
            spaceAfter=2,
        ),
        "firma_meta": ParagraphStyle(
            "firma_meta",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.grey,
            leading=11,
        ),
        "titel": ParagraphStyle(
            "titel",
            parent=base["Heading2"],
            fontSize=14,
            spaceBefore=6,
            spaceAfter=6,
        ),
        "label": ParagraphStyle(
            "label",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.grey,
        ),
        "wert": ParagraphStyle(
            "wert",
            parent=base["Normal"],
            fontSize=10,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.grey,
            alignment=1,  # zentriert
            spaceBefore=10,
        ),
    }


def _trennlinie(story: list) -> None:
    """Dünne horizontale Linie zur optischen Trennung."""
    line = Table(
        [[""]],
        colWidths=[170 * mm],
        rowHeights=[1],
        style=TableStyle(
            [("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.lightgrey)]
        ),
    )
    story.append(Spacer(1, 4 * mm))
    story.append(line)
    story.append(Spacer(1, 4 * mm))


def _kopfzeile(story: list) -> None:
    """Kopf der Quittung — Pizzeria-Name + Kontakt."""
    s = _styles()
    story.append(Paragraph(_PIZZERIA_NAME, s["firma"]))
    story.append(
        Paragraph(
            f"{_PIZZERIA_STRASSE} &nbsp;·&nbsp; {_PIZZERIA_PLZ_ORT}",
            s["firma_meta"],
        )
    )
    story.append(
        Paragraph(
            f"Tel. {_PIZZERIA_TELEFON} &nbsp;·&nbsp; {_PIZZERIA_WEB}",
            s["firma_meta"],
        )
    )


def _titel_und_meta(
    story: list, bestellung: "Bestellung", quittungsnummer: str
) -> None:
    """Block: „QUITTUNG" + Nummer + Datum + Bestell-Nr."""
    s = _styles()
    story.append(Paragraph("QUITTUNG", s["titel"]))

    bestellzeit = bestellung.bestellzeit or datetime.now()
    daten = [
        [Paragraph("Quittungsnummer", s["label"]),
         Paragraph(quittungsnummer, s["wert"])],
        [Paragraph("Datum", s["label"]),
         Paragraph(bestellzeit.strftime("%d.%m.%Y %H:%M"), s["wert"])],
        [Paragraph("Bestell-Nr.", s["label"]),
         Paragraph(str(bestellung.id), s["wert"])],
    ]
    tabelle = Table(daten, colWidths=[40 * mm, 130 * mm])
    tabelle.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    story.append(tabelle)


def _kunde_und_adresse(story: list, bestellung: "Bestellung") -> None:
    """Block: Kunde links, Lieferadresse rechts.

    Liest `bestellung.kunde` und `bestellung.lieferadresse` über die
    Beziehungen des ORM-Modells — funktioniert, weil wir innerhalb
    der Session des `QuittungService` laufen.
    """
    s = _styles()
    kunde = bestellung.kunde
    adresse = bestellung.lieferadresse

    # Kunde-Block als Mini-Tabelle (mehrzeilig, label + wert)
    kunde_zellen = [
        Paragraph("Kunde", s["label"]),
        Paragraph(f"{kunde.vorname} {kunde.nachname}", s["wert"]),
        Paragraph(kunde.email, s["wert"]),
    ]
    if kunde.telefon:
        kunde_zellen.append(Paragraph(kunde.telefon, s["wert"]))
    kunde_block = Table(
        [[zelle] for zelle in kunde_zellen],
        colWidths=[80 * mm],
    )
    kunde_block.setStyle(_block_style())

    # Adresse-Block
    adress_zellen = [
        Paragraph("Lieferadresse", s["label"]),
        Paragraph(f"{adresse.strasse} {adresse.hausnummer}", s["wert"]),
        Paragraph(f"{adresse.plz} {adresse.ort}", s["wert"]),
    ]
    adresse_block = Table(
        [[zelle] for zelle in adress_zellen],
        colWidths=[80 * mm],
    )
    adresse_block.setStyle(_block_style())

    # Beide nebeneinander
    nebeneinander = Table(
        [[kunde_block, adresse_block]],
        colWidths=[85 * mm, 85 * mm],
    )
    nebeneinander.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(nebeneinander)


def _block_style() -> TableStyle:
    """Einheitlicher Style für die Mini-Blöcke (Kunde / Adresse)."""
    return TableStyle(
        [
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]
    )


def _positionen_tabelle(story: list, bestellung: "Bestellung") -> None:
    """Tabelle mit allen Bestell-Positionen.

    Spalten: Position-Beschreibung | Menge | Einzelpreis | Gesamt.
    Wunschpizzas zeigen zusätzlich die gewählten Zutaten in einer
    zweiten Zeile (kleiner und in grau), damit der Kunde sieht, was
    er bestellt hat.
    """
    s = _styles()

    # Kopfzeile
    daten: list[list] = [
        [
            Paragraph("<b>Position</b>", s["wert"]),
            Paragraph("<b>Menge</b>", s["wert"]),
            Paragraph("<b>Einzelpreis</b>", s["wert"]),
            Paragraph("<b>Gesamt</b>", s["wert"]),
        ]
    ]

    for position in bestellung.positionen:
        # Einzelpreis inkl. Zutaten-Aufschlag (für Wunschpizzas)
        zutaten_aufschlag = sum(
            (
                wz.zutat.preis_pro_einheit * (wz.menge or Decimal("1"))
                for wz in position.wunsch_zutaten
            ),
            start=Decimal("0.00"),
        )
        einzelpreis_effektiv = position.einzelpreis + zutaten_aufschlag
        gesamt_position = einzelpreis_effektiv * position.menge

        # Erste Zeile: Artikel-Name + Menge + Preise
        bezeichnung = position.artikel.name
        if position.ist_wunschpizza:
            bezeichnung = f"Wunschpizza ({bezeichnung})"

        zellen = [
            Paragraph(bezeichnung, s["wert"]),
            Paragraph(str(position.menge), s["wert"]),
            Paragraph(
                _chf_format(einzelpreis_effektiv), s["wert"]
            ),
            Paragraph(_chf_format(gesamt_position), s["wert"]),
        ]
        daten.append(zellen)

        # Wenn Wunschpizza: zweite Zeile mit den Zutaten
        if position.ist_wunschpizza and position.wunsch_zutaten:
            zutaten_namen = [wz.zutat.name for wz in position.wunsch_zutaten]
            zutaten_text = "+ " + ", ".join(zutaten_namen)
            daten.append(
                [Paragraph(zutaten_text, s["label"]), "", "", ""]
            )

        # Bemerkung als kleine Zeile darunter, falls vorhanden
        if position.bemerkung:
            daten.append(
                [
                    Paragraph(
                        f'<i>„{position.bemerkung}"</i>', s["label"]
                    ),
                    "",
                    "",
                    "",
                ]
            )

    tabelle = Table(daten, colWidths=[90 * mm, 20 * mm, 30 * mm, 30 * mm])
    tabelle.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ]
        )
    )
    story.append(tabelle)


def _summen_tabelle(story: list, mwst: "MwStAufschluesselung") -> None:
    """Drei-Zeilen-Tabelle: Netto, MwSt, Gesamt.

    Rechtsbündig, damit es wie eine klassische Rechnungs-Summe aussieht.
    """
    s = _styles()

    mwst_satz_prozent = (mwst.mwst_satz * Decimal("100")).normalize()

    daten = [
        [
            Paragraph("Nettobetrag", s["wert"]),
            Paragraph(_chf_format(mwst.netto), s["wert"]),
        ],
        [
            Paragraph(f"MwSt ({mwst_satz_prozent}%)", s["wert"]),
            Paragraph(_chf_format(mwst.mwst), s["wert"]),
        ],
        [
            Paragraph("<b>Gesamtbetrag</b>", s["wert"]),
            Paragraph(f"<b>{_chf_format(mwst.brutto)}</b>", s["wert"]),
        ],
    ]

    tabelle = Table(daten, colWidths=[140 * mm, 30 * mm])
    tabelle.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 0.5, colors.black),
                ("TOPPADDING", (0, 2), (-1, 2), 4),
            ]
        )
    )
    story.append(tabelle)


def _fusszeile(story: list) -> None:
    """Kleiner Dank-Text am Ende der Quittung."""
    s = _styles()
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Vielen Dank für deine Bestellung! Wir freuen uns auf das "
            "nächste Mal.",
            s["footer"],
        )
    )


# ---------------------------------------------------------------------------
# Hilfs-Funktionen
# ---------------------------------------------------------------------------


def _chf_format(betrag: Decimal) -> str:
    """Formatiert einen Betrag als „CHF 12.50".

    Wir benutzen den Punkt als Dezimaltrennzeichen, wie auf den meisten
    Schweizer Quittungen üblich (das Komma kommt eher in Deutschland
    und Österreich vor). Zwei Nachkommastellen sind Pflicht — sonst
    sähe „CHF 12.5" inkonsistent aus.
    """
    return f"CHF {betrag:,.2f}".replace(",", "'")