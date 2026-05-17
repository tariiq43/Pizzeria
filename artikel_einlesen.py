"""
artikel_einlesen.py — Importiert Artikel aus 'Menü Pizzeria.csv' in die DB.

Legt Kategorien automatisch an (Pizza, Getränke, Kaffee, Wein)
und fügt jeden Artikel ein. Bestehende Artikel werden übersprungen,
damit das Skript gefahrlos mehrmals ausgeführt werden kann.
"""

import csv
from decimal import Decimal

from sqlmodel import Session, select

from domain.models import Artikel, Kategorie
from utils.db import engine


CSV_PFAD = "Menü Pizzeria.csv"


def _kategorie_fuer_name(name: str) -> str:
    """Bestimmt die passende Kategorie anhand des Artikelnamens."""
    n = name.lower()
    if "pizza" in n or "wunschpizza" in n:
        return "Pizza"
    if "espresso" in n or "cappuccino" in n:
        return "Kaffee"
    if "wein" in n:
        return "Wein"
    return "Getränke"


def _kategorie_holen_oder_anlegen(
    session: Session, name: str, sortierung: int
) -> Kategorie:
    """Holt eine Kategorie aus der DB oder legt sie neu an."""
    kategorie = session.exec(
        select(Kategorie).where(Kategorie.name == name)
    ).first()
    if kategorie is None:
        kategorie = Kategorie(name=name, sortierung=sortierung)
        session.add(kategorie)
        session.commit()
        session.refresh(kategorie)
        print(f"  Kategorie '{name}' neu angelegt.")
    return kategorie


def importieren() -> None:
    """Liest die CSV und fügt alle Artikel in die DB ein."""
    sortierungen = {"Pizza": 1, "Getränke": 2, "Kaffee": 3, "Wein": 4}

    with Session(engine) as session:
        # Kategorien sicherstellen
        kategorien = {
            name: _kategorie_holen_oder_anlegen(session, name, sort)
            for name, sort in sortierungen.items()
        }

        importiert = 0
        uebersprungen = 0

        with open(CSV_PFAD, mode="r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=";")

            for row in reader:
                name = row["name"].strip()

                bestehend = session.exec(
                    select(Artikel).where(Artikel.name == name)
                ).first()
                if bestehend is not None:
                    uebersprungen += 1
                    continue

                kategorie_name = _kategorie_fuer_name(name)
                kategorie = kategorien[kategorie_name]
                preis = Decimal(row["preis"])

                artikel = Artikel(
                    kategorie_id=kategorie.id,
                    name=name,
                    preis=preis,
                    verfuegbar=True,
                )
                session.add(artikel)
                importiert += 1
                print(f"  + {name}  ({kategorie_name}, CHF {preis})")

            session.commit()

        print()
        print(f"Fertig: {importiert} neu importiert, {uebersprungen} schon vorhanden.")


if __name__ == "__main__":
    importieren()