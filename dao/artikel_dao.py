"""
DAO — Artikel
==============
Datenbank-Zugriff für die Tabelle `artikel`.

Ein Artikel ist ein einzelner Menü-Eintrag (Pizza Margherita, Cola 0.5L,
Tiramisu …). Er gehört genau zu einer Kategorie (`kategorie_id`) und
kann ein Standard-Rezept aus mehreren Zutaten haben (über die Junction-
Tabelle `artikel_zutat` — eigene DAO).

Designentscheidungen:
  - `get_nach_kategorie()` ist eine eigene Methode, weil das die
    häufigste Query in der UI ist (Menü-Seite gruppiert nach Kategorie).
    So bleibt der Service-Code lesbar.
  - `name` ist im Modell NICHT unique (zwei Pizza Margherita in
    verschiedenen Grössen wären erlaubt). Deshalb gibt es kein
    `get_by_name()` mit Single-Result, sondern bei Bedarf eine
    `suchen_nach_name()`-Methode mit Liste.
  - Kein `commit()` in der DAO (gleicher Vertrag wie die anderen DAOs).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from domain.models import Artikel


class ArtikelDAO:
    """Persistenz-Operationen für `Artikel`."""

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    @staticmethod
    def create(session: Session, artikel: Artikel) -> Artikel:
        """Speichert einen neuen Artikel und gibt ihn inkl. ID zurück.

        `flush()` + `refresh()` befüllen die generierte Primary-Key-ID
        sofort. Der Service braucht sie z. B., um direkt danach Standard-
        Zutaten via `ArtikelZutatDAO` zu verknüpfen.

        Hinweis: Die Existenz der `kategorie_id` wird hier nicht geprüft —
        das übernimmt der FK-Constraint der DB. Wer eine schönere
        Fehlermeldung will, prüft im Service vorher mit
        `KategorieDAO.get_by_id()`.
        """
        session.add(artikel)
        session.flush()
        session.refresh(artikel)
        return artikel

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    @staticmethod
    def get_by_id(session: Session, artikel_id: int) -> Optional[Artikel]:
        """Lädt einen Artikel über seine Primary Key.

        Gibt `None` zurück, wenn die ID nicht existiert. Die Service-
        Schicht entscheidet, ob daraus eine Exception oder eine UI-
        Meldung wird.
        """
        return session.get(Artikel, artikel_id)

    @staticmethod
    def get_all(
        session: Session,
        *,
        nur_verfuegbar: bool = False,
        sortiert: bool = True,
    ) -> list[Artikel]:
        """Liefert alle Artikel, optional gefiltert.

        - `nur_verfuegbar=True` blendet ausverkaufte Artikel aus
          (typisch für die Kunden-Menü-Seite, damit nichts bestellt
          werden kann, was die Küche nicht hat).
        - `sortiert=True` sortiert zuerst nach `kategorie_id` (damit
          gleiche Kategorien zusammenstehen) und dann alphabetisch nach
          `name` — gibt eine stabile Reihenfolge in UI und Tests.

        Für die Menü-Anzeige ist `get_nach_kategorie()` meistens
        passender, weil sie pro Kategorie ein eigenes Ergebnis liefert
        und so direkt in einer gruppierten UI verwendet werden kann.
        """
        statement = select(Artikel)
        if nur_verfuegbar:
            statement = statement.where(Artikel.verfuegbar.is_(True))
        if sortiert:
            statement = statement.order_by(Artikel.kategorie_id, Artikel.name)
        return list(session.exec(statement).all())

    @staticmethod
    def get_nach_kategorie(
        session: Session,
        kategorie_id: int,
        *,
        nur_verfuegbar: bool = False,
    ) -> list[Artikel]:
        """Liefert alle Artikel einer Kategorie.

        Hauptverwendung: Menü-Seite. Der Service ruft erst alle
        Kategorien (`KategorieDAO.get_all`) und dann pro Kategorie diese
        Methode auf. Klingt nach N+1, ist aber bei einer Pizzeria mit
        ~5 Kategorien völlig egal — und bleibt dafür einfach lesbar.

        `nur_verfuegbar=True` ist der Default-Wunsch für die Kunden-UI,
        bewusst aber nicht der Default-Wert: Im Admin will man auch
        ausverkaufte Artikel sehen, sonst kann man die Verfügbarkeit
        nicht wieder einschalten.
        """
        statement = select(Artikel).where(Artikel.kategorie_id == kategorie_id)
        if nur_verfuegbar:
            statement = statement.where(Artikel.verfuegbar.is_(True))
        statement = statement.order_by(Artikel.name)
        return list(session.exec(statement).all())

    @staticmethod
    def suchen_nach_name(session: Session, suchbegriff: str) -> list[Artikel]:
        """Sucht Artikel, deren Name den Suchbegriff enthält (case-insensitive).

        Für eine spätere Such-Funktion in der UI. Aktuell nicht zwingend,
        aber günstig und zukunftssicher: Wenn das Team eine Suchleiste
        einbaut, ist die Query schon da. `LIKE` ist für ~30 Artikel
        absolut performant — Volltextsuche brauchen wir nicht.
        """
        # `ilike` macht den Vergleich case-insensitive (SQLite akzeptiert das).
        # `%...%` matcht Substrings, damit „marg" auch „Margherita" findet.
        muster = f"%{suchbegriff}%"
        statement = select(Artikel).where(Artikel.name.ilike(muster)).order_by(Artikel.name)
        return list(session.exec(statement).all())

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    @staticmethod
    def update(session: Session, artikel: Artikel) -> Artikel:
        """Schreibt Änderungen eines bereits geladenen Artikels zurück.

        Erwartet, dass `artikel.id` gesetzt ist. SQLAlchemy erkennt das
        und macht ein UPDATE statt INSERT.

        Achtung: Eine Preisänderung wirkt nur auf neue Bestellungen.
        Alte Bestellpositionen behalten ihren Snapshot-Preis (siehe
        `Bestellposition.einzelpreis` im Domain-Model) — gewollt, damit
        nachträgliche Preisanpassungen alte Quittungen nicht verändern.
        """
        session.add(artikel)
        session.flush()
        session.refresh(artikel)
        return artikel

    @staticmethod
    def verfuegbarkeit_setzen(
        session: Session, artikel_id: int, verfuegbar: bool
    ) -> Optional[Artikel]:
        """Schaltet die Verfügbarkeit eines Artikels um (Convenience-Methode).

        Häufiger Use-Case im Admin: „Pizza Tonno heute aus, kein Thunfisch
        mehr". Statt Artikel laden → mutieren → speichern in einem Aufruf.
        Gibt das aktualisierte Objekt zurück oder `None`, falls die ID
        nicht existiert.
        """
        artikel = session.get(Artikel, artikel_id)
        if artikel is None:
            return None
        artikel.verfuegbar = verfuegbar
        session.add(artikel)
        session.flush()
        session.refresh(artikel)
        return artikel

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    @staticmethod
    def delete(session: Session, artikel_id: int) -> bool:
        """Löscht einen Artikel über seine ID.

        Rückgabe:
          - True, falls ein Artikel gelöscht wurde
          - False, falls die ID nicht existierte

        Achtung: Ein Artikel, der schon in `bestellposition` referenziert
        wird, kann nicht gelöscht werden — der FK-Constraint wirft eine
        IntegrityError. Im Admin sollte man stattdessen
        `verfuegbarkeit_setzen(..., False)` benutzen, damit alte
        Bestellungen ihre Referenz behalten.
        """
        artikel = session.get(Artikel, artikel_id)
        if artikel is None:
            return False
        session.delete(artikel)
        session.flush()
        return True
