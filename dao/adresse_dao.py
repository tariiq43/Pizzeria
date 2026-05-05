"""
AdresseDAO — Pizzeria Sunshine
==============================
Datenzugriff für die Adressen-Tabelle.

Ein Kunde kann mehrere Adressen haben (z. B. Zuhause + Büro). Genau eine
davon kann als "Standard" markiert sein — dafür gibt's eine Helper-Methode
standard_setzen(), die garantiert, dass pro Kunde nicht mehrere Standard-
Adressen gleichzeitig markiert sind.
"""

from typing import List, Optional

from sqlmodel import select

from domain.models import Adresse
from utils.db import get_session


class AdresseDAO:
    """Data Access Object für Adresse-Entities."""

    # ----------------------------------------------------------------------
    # Standard-CRUD
    # ----------------------------------------------------------------------

    @staticmethod
    def create(adresse: Adresse) -> Adresse:
        """Speichert eine neue Adresse für einen Kunden."""
        with get_session() as session:
            session.add(adresse)
            session.commit()
            session.refresh(adresse)
            return adresse

    @staticmethod
    def get_by_id(adress_id: int) -> Optional[Adresse]:
        with get_session() as session:
            return session.get(Adresse, adress_id)

    @staticmethod
    def update(adresse: Adresse) -> Adresse:
        with get_session() as session:
            session.add(adresse)
            session.commit()
            session.refresh(adresse)
            return adresse

    @staticmethod
    def delete(adress_id: int) -> bool:
        """Löscht eine Adresse.

        Achtung: Wenn an dieser Adresse Bestellungen hängen, schlägt das
        wegen Foreign-Key-Constraint fehl. Im Service vorher prüfen oder
        Adresse stattdessen "deaktivieren" (wäre eine Modell-Erweiterung).
        """
        with get_session() as session:
            adresse = session.get(Adresse, adress_id)
            if adresse is None:
                return False
            session.delete(adresse)
            session.commit()
            return True

    # ----------------------------------------------------------------------
    # Spezielle Queries
    # ----------------------------------------------------------------------

    @staticmethod
    def alle_fuer_kunde(kunden_id: int) -> List[Adresse]:
        """Lädt alle Adressen eines bestimmten Kunden.

        Standard-Adresse erscheint zuerst in der Liste — praktisch für die
        UI (z. B. im Checkout-Dropdown). Danach nach id (Reihenfolge der Anlage).
        """
        with get_session() as session:
            statement = (
                select(Adresse)
                .where(Adresse.kunden_id == kunden_id)
                .order_by(Adresse.ist_standard.desc(), Adresse.id)
            )
            return list(session.exec(statement).all())

    @staticmethod
    def standard_fuer_kunde(kunden_id: int) -> Optional[Adresse]:
        """Liefert die als Standard markierte Lieferadresse eines Kunden.

        Falls keine als Standard markiert ist, wird die erste verfügbare
        Adresse zurückgegeben (Fallback). Gibt None zurück, wenn der Kunde
        gar keine Adresse hat — dann muss er im Checkout eine anlegen.
        """
        with get_session() as session:
            # Erst den echten Standard suchen
            statement = select(Adresse).where(
                Adresse.kunden_id == kunden_id,
                Adresse.ist_standard == True,  # noqa: E712 — SQLAlchemy braucht ==
            )
            adresse = session.exec(statement).first()
            if adresse is not None:
                return adresse

            # Fallback: irgendeine Adresse des Kunden
            statement = select(Adresse).where(Adresse.kunden_id == kunden_id)
            return session.exec(statement).first()

    @staticmethod
    def standard_setzen(adress_id: int) -> bool:
        """Markiert eine Adresse als Standard und entfernt das Flag bei
        allen anderen Adressen desselben Kunden.

        Damit ist sichergestellt: pro Kunde existiert höchstens eine Standard-
        Adresse. Diese Logik gehört in die DAO, weil sie mehrere Zeilen in
        einer Transaktion ändert — der Service müsste sich sonst um die
        Konsistenz selbst kümmern.

        Gibt True zurück, wenn erfolgreich; False, wenn die Adresse nicht
        existiert.
        """
        with get_session() as session:
            adresse = session.get(Adresse, adress_id)
            if adresse is None:
                return False

            # Alle anderen Adressen desselben Kunden auf "nicht Standard"
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
            session.commit()
            return True