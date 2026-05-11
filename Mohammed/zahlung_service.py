"""
Service — Zahlung
==================
Business-Logik rund um Zahlungen.

In dieser Schul-App ist die Zahlung gefakt: Jeder Aufruf von
`zahlung_durchfuehren()` ist sofort erfolgreich, eine echte Anbindung
an einen Zahlungsdienst gibt es nicht. Trotzdem geht die Zahlung den
vollen Status-Flow durch (INITIALISIERT -> BEZAHLT), damit:
  - die DB-Daten realistisch aussehen
  - die Quittungs-Erzeugung an einer Stelle ankoppeln kann
  - ein späterer Wechsel auf eine echte API minimal-invasiv ist
    (Implementierung nur in dieser einen Datei tauschen).

Design Pattern: Facade. Der `BestellService` ruft `zahlung_durchfuehren()`
auf und muss nichts vom Zahlungs-Flow wissen. Wenn wir später Stripe
oder TWINT anbinden, ändert sich nur das Innenleben dieser Methode.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlmodel import Session

from dao.zahlung_dao import ZahlungDAO
from domain.models import Zahlung, ZahlungStatus


class ZahlungService:
    """Business-Logik für Zahlungen."""

    @staticmethod
    def zahlung_durchfuehren(
        session: Session,
        bestellung_id: int,
        betrag: Decimal,
        zahlungsmethode: str = "karte",
    ) -> Zahlung:
        """Erzeugt eine Zahlung und markiert sie sofort als BEZAHLT.

        Workflow:
          1. Zahlung mit Status INITIALISIERT anlegen
          2. (in einer echten App: Provider-Call hier)
          3. Status auf BEZAHLT setzen, Transaktions-ID setzen

        Wir machen das in zwei Schritten (anlegen + updaten) statt direkt
        BEZAHLT zu speichern, damit der Datenfluss dem späteren echten
        Ablauf entspricht — bei einem echten Provider würde zwischen
        Schritt 1 und 3 der externe API-Call liegen.

        Parameter `session` wird vom `BestellService` reingegeben, damit
        die Zahlung in derselben Transaktion wie die Bestellung
        persistiert wird (alles oder nichts).

        Wirft `ValueError`, wenn schon eine Zahlung für diese Bestellung
        existiert — Doppel-Bezahlen wäre fachlich falsch.
        """
        # Vorab-Check: existiert schon eine Zahlung für die Bestellung?
        bestehende = ZahlungDAO.finde_per_bestellung(session, bestellung_id)
        if bestehende is not None:
            raise ValueError(
                f"Bestellung {bestellung_id} hat bereits eine Zahlung "
                f"(ID {bestehende.id}, Status {bestehende.status.value})."
            )

        # Schritt 1: Zahlung initialisieren
        zahlung = Zahlung(
            bestellung_id=bestellung_id,
            betrag=betrag,
            zahlungsmethode=zahlungsmethode,
            status=ZahlungStatus.INITIALISIERT,
        )
        zahlung = ZahlungDAO.create(session, zahlung)

        # Schritt 2: hier wäre der echte Provider-Call.
        # Bei uns: Fake-Transaktions-ID, immer erfolgreich.
        fake_transaktions_id = f"FAKE-{uuid.uuid4().hex[:12].upper()}"

        # Schritt 3: Status auf BEZAHLT setzen
        assert zahlung.id is not None
        aktualisiert = ZahlungDAO.status_setzen(
            session,
            zahlung.id,
            ZahlungStatus.BEZAHLT,
            transaktions_id=fake_transaktions_id,
        )
        # status_setzen kann theoretisch None liefern (ID nicht da) —
        # hier unmöglich, weil wir die Zahlung gerade selbst angelegt haben.
        assert aktualisiert is not None
        return aktualisiert
