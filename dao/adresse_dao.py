"""
DAO — Adresse
==============
Datenbank-Zugriff für die Tabelle `adresse`.

Ein Kunde kann mehrere Adressen haben (z. B. Zuhause + Büro). Genau eine
davon kann als „Standard" markiert sein — dafür gibt's eine Helper-Methode
`standard_setzen()`, die garantiert, dass pro Kunde nicht mehrere Standard-
Adressen gleichzeitig markiert sind.

Designentscheidungen:
  - `standard_setzen()` ändert mehrere Zeilen in einer Transaktion. Die
    Logik gehört in die DAO, weil sie sonst auf den Service verteilt
    wäre und dort die Konsistenz pro Aufruf neu sichergestellt werden
    müsste. Hier ist sie an einer Stelle und benutzt dieselbe Session,
    läuft also atomar.
  - `alle_fuer_kunde()` sortiert Standard-Adresse zuerst — typische
    UI-Anforderung (Checkout-Dropdown soll Standard oben haben).
  - Kein `commit()` in der DAO (gleicher Vertrag wie die anderen DAOs).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Adresse


class AdresseDAO:
    """Persistenz-Operationen für `Adresse`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, adresse: Adresse) -> Adresse:
        """Speichert eine neue Adresse und gibt sie inkl. ID zurück.

        `flush()` + `refresh()` setzen die generierte Primary-Key-ID
        sofort am Objekt. So kann der Service die neue Adresse direkt
        z. B. als Standard markieren oder im UI anzeigen.

        Achtung: Wenn `ist_standard=True` gesetzt wird, sollte der Service
        anschliessend `standard_setzen()` aufrufen, um sicherzustellen,
        dass nicht zwei Adressen desselben Kunden gleichzeitig Standard
        sind. (Oder direkt nur `standard_setzen()` — die markiert die
        Adresse als Standard und entfernt das Flag bei allen anderen.)
        """
        session.add(adresse)
        session.flush()
        session.refresh(adresse)
        return adresse

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, adress_id: int) -> Optional[Adresse]:
        """Lädt eine Adresse über ihre Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert.
        """
        return session.get(Adresse, adress_id)

    @staticmethod
    def alle_fuer_kunde(session: Session, kunden_id: int) -> list[Adresse]:
        """Lädt alle Adressen eines bestimmten Kunden.

        Sortierung: Standard-Adresse zuerst (`ist_standard DESC`), danach
        nach `id` (Anlagereihenfolge) — praktisch für das Checkout-
        Dropdown, wo die Standard-Adresse oben stehen soll.
        """
        statement = (
            select(Adresse)
            .where(Adresse.kunden_id == kunden_id)
            .order_by(Adresse.ist_standard.desc(), Adresse.id)
        )
        return list(session.exec(statement).all())

    @staticmethod
    def standard_fuer_kunde(
        session: Session, kunden_id: int
    ) -> Optional[Adresse]:
        """Liefert die als Standard markierte Lieferadresse eines Kunden.

        Falls keine als Standard markiert ist, wird die erste verfügbare
        Adresse zurückgegeben (Fallback) — damit der Checkout nicht ohne
        Vorauswahl dasteht. Gibt `None` zurück, wenn der Kunde gar keine
        Adresse hat — dann muss er im Checkout eine anlegen.
        """
        # Erst die echte Standard-Adresse suchen
        statement = select(Adresse).where(
            Adresse.kunden_id == kunden_id,
            Adresse.ist_standard.is_(True),
        )
        adresse = session.exec(statement).first()
        if adresse is not None:
            return adresse

        # Fallback: irgendeine Adresse des Kunden (älteste zuerst)
        statement = (
            select(Adresse)
            .where(Adresse.kunden_id == kunden_id)
            .order_by(Adresse.id)
        )
        return session.exec(statement).first()

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, adresse: Adresse) -> Adresse:
        """Schreibt Änderungen einer bereits geladenen Adresse zurück.

        Erwartet, dass `adresse.id` gesetzt ist. SQLAlchemy erkennt das
        und macht ein UPDATE statt INSERT.

        Hinweis: Eine Adresse zu mutieren, an der bereits Bestellungen
        hängen, ändert auch deren Liefer-Anschrift in alten Quittungen
        nicht — die speichern die Adresse als Snapshot (siehe Bestell-
        Modell). Für Korrekturen ist das Verhalten gewollt.
        """
        session.add(adresse)
        session.flush()
        session.refresh(adresse)
        return adresse

    @staticmethod
    def standard_setzen(session: Session, adress_id: int) -> bool:
        """Markiert eine Adresse als Standard und entfernt das Flag bei
        allen anderen Adressen desselben Kunden.

        Damit ist sichergestellt: pro Kunde existiert höchstens eine
        Standard-Adresse. Diese Logik gehört in die DAO, weil sie mehrere
        Zeilen in derselben Transaktion ändert — der Service müsste sich
        sonst um die Konsistenz selbst kümmern.

        Rückgabe:
          - True, falls erfolgreich gesetzt
          - False, falls die Adresse nicht existiert
        """
        adresse = session.get(Adresse, adress_id)
        if adresse is None:
            return False

        # Alle anderen Adressen desselben Kunden auf „nicht Standard"
        statement = select(Adresse).where(
            Adresse.kunden_id == adresse.kunden_id,
            Adresse.id != adress_id,
        )
        for andere in session.exec(statement).all():
            andere.ist_standard = False
            session.add(andere)

        # Die gewünschte Adresse als Standard
        adresse.ist_standard = True
        session.add(adresse)
        session.flush()
        return True

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, adress_id: int) -> bool:
        """Löscht eine Adresse über ihre ID.

        Rückgabe:
          - True, falls eine Adresse gelöscht wurde
          - False, falls die ID nicht existierte

        Achtung: Wenn an dieser Adresse Bestellungen hängen, schlägt das
        wegen Foreign-Key-Constraint fehl. Im Service vorher prüfen oder
        die Adresse stattdessen als „nicht aktiv" markieren (wäre eine
        Modell-Erweiterung).
        """
        adresse = session.get(Adresse, adress_id)
        if adresse is None:
            return False
        session.delete(adresse)
        session.flush()
        return True