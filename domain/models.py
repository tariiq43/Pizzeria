"""
Domain Model — Pizzeria Sunshine
================================
Alle SQLModel-Entities für die Pizzeria-App.
 
Diese Datei enthält die 12 Tabellen aus dem ER-Modell. Jede Klasse ist
gleichzeitig:
  - SQLModel-Tabelle (table=True) -> wird in SQLite persistiert
  - Pydantic-Model -> kann validiert und serialisiert werden
  - Domain-Klasse -> hat Methoden mit Business-Logik (siehe UML-Diagramm)
 
Verwendet von allen Schichten (UI, Services, DAOs).
"""
 
from __future__ import annotations
 
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
 
from sqlmodel import Field, Relationship, SQLModel
 
 
# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
 
 
class MitarbeiterRolle(str, Enum):
    """Rollen für Mitarbeiter (für /admin-Zugriff)."""
 
    KOCH = "koch"
    FAHRER = "fahrer"
    ADMIN = "admin"
 
 
class BestellStatus(str, Enum):
    """Status einer Bestellung im Bearbeitungsfluss."""
 
    OFFEN = "offen"
    IN_BEARBEITUNG = "in_bearbeitung"
    UNTERWEGS = "unterwegs"
    GELIEFERT = "geliefert"
    STORNIERT = "storniert"
 
 
class ZahlungStatus(str, Enum):
    """Status einer Zahlung."""
 
    INITIALISIERT = "initialisiert"
    BEZAHLT = "bezahlt"
    FEHLGESCHLAGEN = "fehlgeschlagen"
 
 
# ---------------------------------------------------------------------------
# Personen-Entities: Kunde, Adresse, Mitarbeiter
# ---------------------------------------------------------------------------
 
 
class Kunde(SQLModel, table=True):
    """Endkunde, der Bestellungen aufgibt."""
 
    __tablename__ = "kunde"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    vorname: str
    nachname: str
    email: str = Field(index=True, unique=True)
    telefon: Optional[str] = None
    passwort_hash: str  # via passlib/bcrypt
    erstellt_am: datetime = Field(default_factory=datetime.utcnow)
 
    # Beziehungen
    adressen: list["Adresse"] = Relationship(back_populates="kunde")
    bestellungen: list["Bestellung"] = Relationship(back_populates="kunde")
 
    # --- Methoden (siehe UML) ---
    def passwort_pruefen(self, klartext: str) -> bool:
        """Vergleicht ein Klartext-Passwort mit dem gespeicherten Hash.
 
        Die eigentliche Hash-Logik liegt im AuthService (passlib).
        Diese Methode delegiert nur — so bleibt das Model frei von I/O.
        """
        from passlib.hash import bcrypt  # lokaler Import, damit Tests einfacher sind
 
        return bcrypt.verify(klartext, self.passwort_hash)
 
    def voller_name(self) -> str:
        return f"{self.vorname} {self.nachname}"
 
 
class Adresse(SQLModel, table=True):
    """Lieferadresse eines Kunden. Ein Kunde kann mehrere Adressen haben."""
 
    __tablename__ = "adresse"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    kunden_id: int = Field(foreign_key="kunde.id")
    strasse: str
    hausnummer: str
    plz: str
    ort: str
    ist_standard: bool = Field(default=False)
 
    # Beziehungen
    kunde: Optional[Kunde] = Relationship(back_populates="adressen")
    bestellungen: list["Bestellung"] = Relationship(back_populates="lieferadresse")
 
    def als_text(self) -> str:
        return f"{self.strasse} {self.hausnummer}, {self.plz} {self.ort}"
 
 
class Mitarbeiter(SQLModel, table=True):
    """Mitarbeiter der Pizzeria (Koch, Fahrer, Admin)."""
 
    __tablename__ = "mitarbeiter"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    vorname: str
    nachname: str
    email: str = Field(index=True, unique=True)
    passwort_hash: str
    rolle: MitarbeiterRolle = Field(default=MitarbeiterRolle.KOCH)
    aktiv: bool = Field(default=True)
 
    # Beziehungen
    bestellungen: list["Bestellung"] = Relationship(back_populates="mitarbeiter")
 
    def passwort_pruefen(self, klartext: str) -> bool:
        from passlib.hash import bcrypt
 
        return bcrypt.verify(klartext, self.passwort_hash)
 
    def ist_admin(self) -> bool:
        return self.rolle == MitarbeiterRolle.ADMIN
 
 
# ---------------------------------------------------------------------------
# Menü-Entities: Kategorie, Artikel, Zutat, ArtikelZutat
# ---------------------------------------------------------------------------
 
 
class Kategorie(SQLModel, table=True):
    """Menü-Kategorie (z. B. Pizza, Pasta, Getränke)."""
 
    __tablename__ = "kategorie"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    beschreibung: Optional[str] = None
    sortierung: int = Field(default=0)  # für die Reihenfolge in der UI
 
    artikel: list["Artikel"] = Relationship(back_populates="kategorie")
 
 
class Artikel(SQLModel, table=True):
    """Einzelner Menü-Artikel (Pizza, Getränk, etc.)."""
 
    __tablename__ = "artikel"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    kategorie_id: int = Field(foreign_key="kategorie.id")
    name: str
    beschreibung: Optional[str] = None
    preis: Decimal = Field(max_digits=8, decimal_places=2)
    verfuegbar: bool = Field(default=True)
    bild_url: Optional[str] = None
 
    # Beziehungen
    kategorie: Optional[Kategorie] = Relationship(back_populates="artikel")
    artikel_zutaten: list["ArtikelZutat"] = Relationship(back_populates="artikel")
    bestellpositionen: list["Bestellposition"] = Relationship(back_populates="artikel")
 
 
class Zutat(SQLModel, table=True):
    """Zutat für Pizzas (Käse, Salami, Pilze, ...)."""
 
    __tablename__ = "zutat"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    preis_pro_einheit: Decimal = Field(max_digits=6, decimal_places=2)
    einheit: str = Field(default="Portion")  # z. B. "Portion", "Gramm"
    vegetarisch: bool = Field(default=True)
    verfuegbar: bool = Field(default=True)
 
    # Beziehungen
    artikel_zutaten: list["ArtikelZutat"] = Relationship(back_populates="zutat")
    wunsch_zutaten: list["WunschZutat"] = Relationship(back_populates="zutat")
 
 
class ArtikelZutat(SQLModel, table=True):
    """Junction-Tabelle: Standard-Rezept eines Artikels.
 
    z. B. "Pizza Margherita enthält Käse (Menge 1), Tomatensauce (Menge 1)".
    """
 
    __tablename__ = "artikel_zutat"
 
    artikel_id: int = Field(foreign_key="artikel.id", primary_key=True)
    zutat_id: int = Field(foreign_key="zutat.id", primary_key=True)
    menge: Decimal = Field(default=Decimal("1"), max_digits=6, decimal_places=2)
 
    # Beziehungen
    artikel: Optional[Artikel] = Relationship(back_populates="artikel_zutaten")
    zutat: Optional[Zutat] = Relationship(back_populates="artikel_zutaten")
 
 
# ---------------------------------------------------------------------------
# Bestell-Entities: Bestellung, Bestellposition, WunschZutat
# ---------------------------------------------------------------------------
 
 
class Bestellung(SQLModel, table=True):
    """Eine Kundenbestellung (Kopf-Datensatz)."""
 
    __tablename__ = "bestellung"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    kunden_id: int = Field(foreign_key="kunde.id")
    lieferadresse_id: int = Field(foreign_key="adresse.id")
    mitarbeiter_id: Optional[int] = Field(default=None, foreign_key="mitarbeiter.id")
    bestellzeit: datetime = Field(default_factory=datetime.utcnow)
    status: BestellStatus = Field(default=BestellStatus.OFFEN)
    gesamtbetrag: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    bemerkung: Optional[str] = None
 
    # Beziehungen
    kunde: Optional[Kunde] = Relationship(back_populates="bestellungen")
    lieferadresse: Optional[Adresse] = Relationship(back_populates="bestellungen")
    mitarbeiter: Optional[Mitarbeiter] = Relationship(back_populates="bestellungen")
    positionen: list["Bestellposition"] = Relationship(back_populates="bestellung")
    quittung: Optional["Quittung"] = Relationship(back_populates="bestellung")
    zahlung: Optional["Zahlung"] = Relationship(back_populates="bestellung")
 
    # --- Methoden (siehe UML) ---
    def gesamtbetrag_berechnen(self) -> Decimal:
        """Summiert alle Bestellpositionen und schreibt das Ergebnis ins Feld."""
        summe = sum(
            (p.positionsbetrag_berechnen() for p in self.positionen),
            start=Decimal("0.00"),
        )
        self.gesamtbetrag = summe
        return summe
 
 
class Bestellposition(SQLModel, table=True):
    """Eine Position in einer Bestellung (z. B. 2x Pizza Salami).
 
    Speichert einen Snapshot des Einzelpreises zum Bestellzeitpunkt,
    damit nachträgliche Preisänderungen alte Bestellungen nicht verändern.
    """
 
    __tablename__ = "bestellposition"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    bestellung_id: int = Field(foreign_key="bestellung.id")
    artikel_id: int = Field(foreign_key="artikel.id")
    menge: int = Field(default=1)
    einzelpreis: Decimal = Field(max_digits=8, decimal_places=2)  # Snapshot
    ist_wunschpizza: bool = Field(default=False)
    bemerkung: Optional[str] = None
 
    # Beziehungen
    bestellung: Optional[Bestellung] = Relationship(back_populates="positionen")
    artikel: Optional[Artikel] = Relationship(back_populates="bestellpositionen")
    wunsch_zutaten: list["WunschZutat"] = Relationship(back_populates="bestellposition")
 
    # --- Methoden (siehe UML) ---
    def positionsbetrag_berechnen(self) -> Decimal:
        """menge × einzelpreis. Bei Wunschpizza inkl. Zutaten-Aufschlag."""
        basis = Decimal(self.menge) * self.einzelpreis
        if self.ist_wunschpizza and self.wunsch_zutaten:
            zutaten_summe = sum(
                (wz.zutat.preis_pro_einheit for wz in self.wunsch_zutaten if wz.zutat),
                start=Decimal("0.00"),
            )
            basis += Decimal(self.menge) * zutaten_summe
        return basis
 
 
class WunschZutat(SQLModel, table=True):
    """Junction-Tabelle: Zutaten einer Wunschpizza (Bestellposition <-> Zutat).
 
    Wird nur befüllt, wenn Bestellposition.ist_wunschpizza == True.
    """
 
    __tablename__ = "wunsch_zutat"
 
    bestellposition_id: int = Field(foreign_key="bestellposition.id", primary_key=True)
    zutat_id: int = Field(foreign_key="zutat.id", primary_key=True)
    menge: Decimal = Field(default=Decimal("1"), max_digits=6, decimal_places=2)
 
    # Beziehungen
    bestellposition: Optional[Bestellposition] = Relationship(back_populates="wunsch_zutaten")
    zutat: Optional[Zutat] = Relationship(back_populates="wunsch_zutaten")
 
 
# ---------------------------------------------------------------------------
# Nachgelagerte Entities: Quittung, Zahlung
# ---------------------------------------------------------------------------
 
 
class Quittung(SQLModel, table=True):
    """Quittung zu einer Bestellung. 1:1 zur Bestellung."""
 
    __tablename__ = "quittung"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    bestellung_id: int = Field(foreign_key="bestellung.id", unique=True)
    quittungsnummer: str = Field(unique=True, index=True)
    erstellt_am: datetime = Field(default_factory=datetime.utcnow)
    pdf_pfad: Optional[str] = None  # Pfad zur generierten PDF-Datei
 
    # Beziehungen
    bestellung: Optional[Bestellung] = Relationship(back_populates="quittung")
 
    # --- Methoden (siehe UML) ---
    def als_pdf_speichern(self, ziel_pfad: str) -> str:
        """Erzeugt die Quittungs-PDF via reportlab.
 
        Implementierung steht im QuittungService — diese Methode bleibt
        eine Fassade, damit das Model selbst keine Datei-I/O hat.
        """
        from utils.pdf_generator import quittung_als_pdf
 
        quittung_als_pdf(self, ziel_pfad)
        self.pdf_pfad = ziel_pfad
        return ziel_pfad
 
 
class Zahlung(SQLModel, table=True):
    """Zahlung zu einer Bestellung. 1:1 zur Bestellung."""
 
    __tablename__ = "zahlung"
 
    id: Optional[int] = Field(default=None, primary_key=True)
    bestellung_id: int = Field(foreign_key="bestellung.id", unique=True)
    betrag: Decimal = Field(max_digits=10, decimal_places=2)
    zahlungsmethode: str  # "karte", "twint", "rechnung"
    status: ZahlungStatus = Field(default=ZahlungStatus.INITIALISIERT)
    transaktions_id: Optional[str] = None
    erstellt_am: datetime = Field(default_factory=datetime.utcnow)
 
    # Beziehungen
    bestellung: Optional[Bestellung] = Relationship(back_populates="zahlung")
 
    def ist_bezahlt(self) -> bool:
        return self.status == ZahlungStatus.BEZAHLT