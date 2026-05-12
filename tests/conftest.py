"""
Pytest-Fixtures
================
Gemeinsame Test-Hilfen für DAO- und Service-Tests.

Konzept:
  - Jeder Test bekommt eine frische In-Memory-SQLite-Datenbank. Damit
    sind Tests isoliert: keine Reihenfolge-Abhängigkeit, kein Aufräumen
    nötig, keine `pizzeria.db`-Datei wird beschrieben.
  - `StaticPool` ist wichtig, weil `:memory:`-SQLite sonst pro
    Connection eine eigene Datenbank ist (würde leer wirken).
  - `utils.db.engine` wird via `monkeypatch` ausgetauscht, damit
    `get_session()` (und alles, was es benutzt — also der Service)
    automatisch gegen die Test-DB läuft. Kein Code-Pfad muss umgebaut
    werden, nur damit er testbar ist.

Wer einen Test schreibt:
  - Für DAO-Tests: `db_session` reinziehen — das ist eine Session,
    direkt am Test-Engine.
  - Für Service-Tests: `db_engine` reicht (Service öffnet seine
    Session selbst).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from domain import models  # noqa: F401  -> registriert alle Tabellen in metadata
from domain.models import Artikel, Kategorie, Zutat


# ---------------------------------------------------------------------------
# DB-Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine(monkeypatch):
    """Frische In-Memory-Engine pro Test, ersetzt auch `utils.db.engine`.

    Schritte:
      1. Engine erzeugen (StaticPool!).
      2. FK-Constraints aktivieren — damit verhalten sich die Tests wie
         die Produktiv-DB (Cascade, IntegrityError bei verbotenen
         Löschungen).
      3. Schema anlegen.
      4. `utils.db.engine` patchen, sodass `get_session()` aus dem
         Service-Code transparent die Test-DB benutzt.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _foreign_keys_aktivieren(dbapi_connection, _record) -> None:
        # Gleicher PRAGMA-Setup wie in `utils/db.py`. Ohne den lassen
        # wir die FK-Tests „grün" werden, obwohl sie es real nicht wären.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(test_engine)

    # Modul lokal importieren, damit der Patch erst greift, wenn die
    # Test-Engine wirklich steht.
    from utils import db as db_module

    monkeypatch.setattr(db_module, "engine", test_engine)

    yield test_engine

    test_engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Eine offene Session am Test-Engine — bequem für DAO-Tests.

    Wir committen pro Aufruf manuell (in den DAO-Tests). Für Konsistenz
    mit `get_session()` schliessen wir die Session am Ende.
    """
    with Session(db_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Daten-Fixtures (kleine Beispiel-Stammdaten)
# ---------------------------------------------------------------------------
# Diese Fixtures legen Daten direkt via Session an, NICHT via DAO. Wir
# wollen Fixtures unabhängig vom getesteten Code halten — sonst würde
# ein DAO-Bug zu kaskadierenden Fehlschlägen führen, die schwer zu lesen
# sind.


@pytest.fixture
def kategorie_pizzen(db_session) -> Kategorie:
    """Beispiel-Kategorie 'Pizzen'."""
    kategorie = Kategorie(name="Pizzen", beschreibung="Klassiker", sortierung=1)
    db_session.add(kategorie)
    db_session.commit()
    db_session.refresh(kategorie)
    return kategorie


@pytest.fixture
def kategorie_getraenke(db_session) -> Kategorie:
    """Beispiel-Kategorie 'Getränke'."""
    kategorie = Kategorie(name="Getränke", sortierung=2)
    db_session.add(kategorie)
    db_session.commit()
    db_session.refresh(kategorie)
    return kategorie


@pytest.fixture
def zutat_mozzarella(db_session) -> Zutat:
    """Beispiel-Zutat 'Mozzarella'."""
    zutat = Zutat(
        name="Mozzarella",
        preis_pro_einheit=Decimal("2.50"),
        einheit="Portion",
        vegetarisch=True,
        verfuegbar=True,
    )
    db_session.add(zutat)
    db_session.commit()
    db_session.refresh(zutat)
    return zutat


@pytest.fixture
def zutat_salami(db_session) -> Zutat:
    """Beispiel-Zutat 'Salami' (nicht vegetarisch)."""
    zutat = Zutat(
        name="Salami",
        preis_pro_einheit=Decimal("3.00"),
        einheit="Portion",
        vegetarisch=False,
        verfuegbar=True,
    )
    db_session.add(zutat)
    db_session.commit()
    db_session.refresh(zutat)
    return zutat


@pytest.fixture
def artikel_margherita(db_session, kategorie_pizzen) -> Artikel:
    """Beispiel-Artikel 'Pizza Margherita' in Kategorie 'Pizzen'."""
    artikel = Artikel(
        name="Margherita",
        kategorie_id=kategorie_pizzen.id,
        preis=Decimal("14.50"),
        beschreibung="Tomaten, Mozzarella, Basilikum",
        verfuegbar=True,
    )
    db_session.add(artikel)
    db_session.commit()
    db_session.refresh(artikel)
    return artikel
