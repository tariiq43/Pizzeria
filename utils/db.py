"""
Datenbank-Setup — Pizzeria Sunshine
====================================
Engine, Session-Factory und Schema-Initialisierung für die SQLite-DB.

Diese Datei ist der einzige Ort, an dem die SQLAlchemy-Engine erzeugt wird.
Alle DAOs holen ihre Session über `get_session()` — so bleibt der
Persistenz-Mechanismus an einer Stelle gekapselt. Würden wir später z. B.
auf PostgreSQL wechseln, müssten wir nur diese Datei anfassen, nicht die
DAOs.

Warum SQLite?
  - Eine Datei, kein Server -> einfach für ein Studienprojekt
  - SQLModel/SQLAlchemy unterstützt es out-of-the-box
  - PRAGMA foreign_keys=ON ist nötig, weil SQLite FK-Constraints
    sonst stillschweigend ignoriert (siehe `_foreign_keys_aktivieren`)
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------


# Pfad zur DB-Datei: liegt im Projekt-Root (Eltern von utils/).
# Über die Variable lässt sich der Pfad in Tests einfach umbiegen
# (z. B. auf eine temporäre Datei oder ":memory:").
DB_PATH: Path = Path(__file__).resolve().parent.parent / "pizzeria.db"

# SQLAlchemy-URL für SQLite.
# `check_same_thread=False` ist nötig, weil NiceGUI mehrere Threads benutzt.
# Da jede DAO-Operation ihre eigene Session öffnet und sofort wieder
# schliesst, entstehen dadurch keine Race-Conditions.
DATABASE_URL: str = f"sqlite:///{DB_PATH}"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


# echo=False, damit die Konsole nicht mit SQL-Statements geflutet wird.
# Wer beim Debuggen mitlesen will, setzt es lokal kurz auf True.
engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _foreign_keys_aktivieren(dbapi_connection, connection_record) -> None:
    """Aktiviert FK-Constraints für jede neue SQLite-Verbindung.

    SQLite kennt Foreign Keys, schaltet die Prüfung per Default aber AUS.
    Ohne diesen PRAGMA-Befehl würden Inserts mit ungültigen FK-Werten
    durchrutschen — gerade unsere Junction-Tabellen `artikel_zutat` und
    `wunsch_zutat` würden dadurch ihre Datenintegrität verlieren.

    Der Event-Listener läuft automatisch bei jedem `engine.connect()`,
    sodass wir das nicht in jedem DAO wiederholen müssen.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Schema-Initialisierung
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Erzeugt alle Tabellen, falls sie noch nicht existieren.

    Wird einmalig beim App-Start (in `app.py`) aufgerufen.
    `SQLModel.metadata` kennt automatisch alle Klassen, die mit
    `table=True` deklariert wurden — vorausgesetzt, das Modul
    `domain.models` wurde vorher importiert.

    Der lokale Import unten erzwingt genau das: Auch wenn der Aufrufer
    `models` selbst noch nicht importiert hat, sind die Tabellen vor
    `create_all()` registriert. So vermeiden wir reihenfolgeabhängige
    Bugs beim ersten Start.
    """
    # Lokaler Import, damit alle SQLModel-Klassen registriert sind,
    # bevor `metadata.create_all()` läuft.
    from domain import models  # noqa: F401  (Import nur für Side-Effect)

    SQLModel.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Session-Factory
# ---------------------------------------------------------------------------


@contextmanager
def get_session() -> Iterator[Session]:
    """Liefert eine Datenbank-Session als Context-Manager.

    Vorteil gegenüber `Session(engine)` direkt:
      - Commit erfolgt automatisch am Ende des `with`-Blocks
      - Rollback bei jeder Exception (kein halb-geschriebener Zustand)
      - Session wird garantiert geschlossen (auch im Fehlerfall)

    Die Transaktions-Grenze liegt damit pro `with`-Block. In den DAOs
    bedeutet das: Jede einzelne CRUD-Operation ist eine eigene
    Transaktion. Wer mehrere Operationen atomar ausführen will (z. B.
    im Service-Layer), öffnet eine einzige `get_session()` und reicht
    die Session an mehrere DAO-Methoden weiter.

    Verwendung:
        with get_session() as session:
            kategorie = session.get(Kategorie, 1)
    """
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        # Bei Fehlern alles zurückrollen, damit die DB konsistent bleibt.
        # Das Re-Raise erhält den Original-Stacktrace für den Aufrufer.
        session.rollback()
        raise
    finally:
        session.close()
