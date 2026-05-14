"""
KundenService — Pizzeria Sunshine
==================================
Geschäftslogik rund um den Kunden-Account: Profil ansehen / bearbeiten
und Lieferadressen verwalten.

Was NICHT hier liegt:
  - Login, Registrierung, Passwort-Änderung → `AuthService`.
  - Bestellungen, Warenkorb, Checkout → `BestellungService`
    (verantwortlich: Mohammed). `bestellhistorie()` delegiert da hin,
    sobald sein Service steht — bis dahin als TODO markiert.
  - Quittungen → `QuittungService`.

Trennung Service vs. DAO:
  - DAO kennt nur SQL/ORM. Sie weiss nicht, was eine „Standard-Adresse"
    bedeutet, sondern nur, wie man das Flag setzt.
  - Service kennt die Geschäftsregeln (z. B. „Wenn der Kunde seine
    einzige Adresse löscht, muss er beim nächsten Checkout eine neue
    anlegen") und das Transaktionsverhalten.

Designentscheidungen:
  - **Eine Methode = eine Transaktion.** Jede Service-Methode öffnet
    via `get_session()` ihre eigene Session. Wer mehrere Service-Aufrufe
    in einer Transaktion bündeln will, müsste das eine Ebene höher tun
    (gibt's bei uns aktuell nicht — die UI ruft pro Aktion genau einen
    Service auf).
  - **Email-Änderung ist heikel** und gehört NICHT in `profil_aktualisieren`.
    Wenn das später kommt, wird das eine eigene Methode mit Passwort-
    Bestätigung (analog `passwort_aendern_kunde`) — sonst könnte ein
    offener Browser-Tab die Email kapern.
  - **`adresse_hinzufuegen` setzt automatisch die erste Adresse als
    Standard.** Sonst hätte der Kunde keine ausgewählte Liefer-Adresse,
    und der Checkout müsste sich darum kümmern. Lieber hier einmal
    sauber als an drei Stellen halb.
  - **`adresse_loeschen` prüft NICHT, ob noch Bestellungen dranhängen.**
    Das ist ein FK-Constraint im Modell und wird von der DB erzwungen.
    Wer das eleganter abfangen will, fängt die `IntegrityError` in der
    UI ab und zeigt eine Meldung.
  - Rückgabe-Konvention: Mutierende Operationen geben das geänderte
    Objekt zurück (oder `bool` bei Lösch-Aktionen). `None` heisst „nicht
    gefunden", `ValueError` heisst „Eingabe war ungültig".
"""

from __future__ import annotations

from typing import Optional

from dao.adresse_dao import AdresseDAO
from dao.kunden_dao import KundenDAO
from domain.models import Adresse, Kunde
from utils.db import get_session


class KundenService:
    """Service für Profil- und Adress-Verwaltung eines Kunden."""

    # -----------------------------------------------------------------------
    # Profil — Lesen
    # -----------------------------------------------------------------------

    @staticmethod
    def get_profil(kunden_id: int) -> Optional[Kunde]:
        """Lädt den Kunden anhand seiner ID.

        Wird typischerweise nach dem Login aufgerufen, um auf der Profil-
        Seite Name, Email und Telefonnummer anzuzeigen. Gibt `None`
        zurück, wenn die ID nicht existiert (z. B. weil der Kunde
        zwischenzeitlich gelöscht wurde).
        """
        with get_session() as session:
            return KundenDAO.get_by_id(session, kunden_id)

    # -----------------------------------------------------------------------
    # Profil — Bearbeiten
    # -----------------------------------------------------------------------

    @staticmethod
    def profil_aktualisieren(
        kunden_id: int,
        *,
        vorname: Optional[str] = None,
        nachname: Optional[str] = None,
        telefon: Optional[str] = None,
    ) -> Optional[Kunde]:
        """Aktualisiert die Stammdaten eines Kunden.

        Alle Felder sind optional (keyword-only) — die UI schickt nur,
        was geändert wurde. `None` heisst „nicht ändern", ein leerer
        String heisst „ungültig" (wird als `ValueError` abgewiesen, ausser
        beim Telefon: dort heisst leer „löschen").

        Rückgabe:
          - aktualisierter Kunde,
          - `None`, wenn die ID nicht existiert.

        Hinweis: Email-Änderung wird hier bewusst NICHT unterstützt —
        siehe Modul-Docstring.
        """
        if vorname is not None and not vorname.strip():
            raise ValueError("Vorname darf nicht leer sein.")
        if nachname is not None and not nachname.strip():
            raise ValueError("Nachname darf nicht leer sein.")

        with get_session() as session:
            kunde = KundenDAO.get_by_id(session, kunden_id)
            if kunde is None:
                return None

            if vorname is not None:
                kunde.vorname = vorname.strip()
            if nachname is not None:
                kunde.nachname = nachname.strip()
            if telefon is not None:
                # Leerer String => Telefon entfernen (auf NULL setzen)
                kunde.telefon = telefon.strip() or None

            return KundenDAO.update(session, kunde)

    # -----------------------------------------------------------------------
    # Adressen — Lesen
    # -----------------------------------------------------------------------

    @staticmethod
    def alle_adressen(kunden_id: int) -> list[Adresse]:
        """Liefert alle Adressen eines Kunden (Standard zuerst).

        Wird im Kunden-Konto („Meine Adressen") und im Checkout
        verwendet. Die Sortierung kommt aus `AdresseDAO.alle_fuer_kunde`.
        """
        with get_session() as session:
            return AdresseDAO.alle_fuer_kunde(session, kunden_id)

    @staticmethod
    def standard_adresse(kunden_id: int) -> Optional[Adresse]:
        """Liefert die Standard-Lieferadresse eines Kunden (mit Fallback).

        Wenn keine als Standard markiert ist, gibt die DAO die älteste
        Adresse zurück — siehe `AdresseDAO.standard_fuer_kunde`. `None`
        nur, wenn der Kunde gar keine Adresse hat (dann muss er im
        Checkout eine anlegen).
        """
        with get_session() as session:
            return AdresseDAO.standard_fuer_kunde(session, kunden_id)

    # -----------------------------------------------------------------------
    # Adressen — Schreiben
    # -----------------------------------------------------------------------

    @staticmethod
    def adresse_hinzufuegen(
        kunden_id: int,
        *,
        strasse: str,
        hausnummer: str,
        plz: str,
        ort: str,
        als_standard: bool = False,
    ) -> Adresse:
        """Legt eine neue Adresse für den Kunden an.

        Geschäftsregel: Wenn der Kunde noch GAR KEINE Adresse hat, wird
        die neue automatisch zur Standard-Adresse — egal, was
        `als_standard` sagt. Sonst gäbe es im Checkout keinen Default.

        Wenn `als_standard=True` (explizit gewünscht oder erste Adresse),
        wird `standard_setzen()` aufgerufen — die DAO sorgt dafür, dass
        keine andere Adresse desselben Kunden gleichzeitig Standard ist.

        Wirft `ValueError` bei leeren Pflichtfeldern. PLZ-/Hausnummer-
        Format wird hier nicht geprüft (die UI macht das per
        Input-Validation; eine reine Backend-Prüfung wäre für ein
        Schweizer Pizza-Liefergebiet ohnehin Overkill).
        """
        if not strasse.strip():
            raise ValueError("Strasse darf nicht leer sein.")
        if not hausnummer.strip():
            raise ValueError("Hausnummer darf nicht leer sein.")
        if not plz.strip():
            raise ValueError("PLZ darf nicht leer sein.")
        if not ort.strip():
            raise ValueError("Ort darf nicht leer sein.")

        with get_session() as session:
            # Wenn der Kunde noch keine Adresse hat, ist die neue immer Standard
            bestehende = AdresseDAO.alle_fuer_kunde(session, kunden_id)
            erste_adresse = len(bestehende) == 0
            als_standard_effektiv = als_standard or erste_adresse

            adresse = Adresse(
                kunden_id=kunden_id,
                strasse=strasse.strip(),
                hausnummer=hausnummer.strip(),
                plz=plz.strip(),
                ort=ort.strip(),
                ist_standard=als_standard_effektiv,
            )
            adresse = AdresseDAO.create(session, adresse)

            # Wenn Standard gesetzt werden soll, über die DAO-Methode laufen,
            # damit das Flag bei allen anderen Adressen entfernt wird.
            if als_standard_effektiv:
                AdresseDAO.standard_setzen(session, adresse.id)

            return adresse

    @staticmethod
    def adresse_aktualisieren(
        adress_id: int,
        *,
        strasse: Optional[str] = None,
        hausnummer: Optional[str] = None,
        plz: Optional[str] = None,
        ort: Optional[str] = None,
    ) -> Optional[Adresse]:
        """Aktualisiert eine bestehende Adresse.

        Nur die übergebenen Felder werden geändert (keyword-only,
        Default `None` = „nicht ändern"). Leere Strings sind ungültig
        und werden mit `ValueError` abgewiesen — Adress-Felder sind
        Pflichtfelder.

        Achtung: Alte Bestellungen, die auf diese Adresse zeigen, sehen
        die Änderung NICHT — die haben die Adresse als Snapshot
        gespeichert (siehe Bestell-Modell von Mohammed). Damit bleibt
        die Quittung historisch korrekt.

        Rückgabe:
          - aktualisierte Adresse,
          - `None`, wenn die ID nicht existiert.
        """
        # Validierung vor dem DB-Zugriff
        for name, wert in (
            ("Strasse", strasse),
            ("Hausnummer", hausnummer),
            ("PLZ", plz),
            ("Ort", ort),
        ):
            if wert is not None and not wert.strip():
                raise ValueError(f"{name} darf nicht leer sein.")

        with get_session() as session:
            adresse = AdresseDAO.get_by_id(session, adress_id)
            if adresse is None:
                return None

            if strasse is not None:
                adresse.strasse = strasse.strip()
            if hausnummer is not None:
                adresse.hausnummer = hausnummer.strip()
            if plz is not None:
                adresse.plz = plz.strip()
            if ort is not None:
                adresse.ort = ort.strip()

            return AdresseDAO.update(session, adresse)

    @staticmethod
    def standard_adresse_setzen(adress_id: int) -> bool:
        """Markiert eine Adresse als Standard-Lieferadresse.

        Die DAO sorgt dafür, dass keine andere Adresse desselben Kunden
        gleichzeitig Standard ist (atomar in derselben Transaktion).

        Rückgabe:
          - True, wenn erfolgreich,
          - False, wenn die Adresse nicht existiert.
        """
        with get_session() as session:
            return AdresseDAO.standard_setzen(session, adress_id)

    @staticmethod
    def adresse_loeschen(adress_id: int) -> bool:
        """Löscht eine Adresse.

        Wenn die gelöschte Adresse die Standard-Adresse war, hat der
        Kunde danach evtl. keine Standard-Adresse mehr — der nächste
        Checkout zeigt dann die älteste verbleibende Adresse als
        Fallback (siehe `AdresseDAO.standard_fuer_kunde`).

        Rückgabe:
          - True, wenn gelöscht,
          - False, wenn die ID nicht existierte.

        Wirft `IntegrityError` (vom DB-Layer), falls noch Bestellungen
        auf diese Adresse zeigen — siehe Modul-Docstring.
        """
        with get_session() as session:
            return AdresseDAO.delete(session, adress_id)

    # -----------------------------------------------------------------------
    # Bestellhistorie — Delegation an das Bestell-Team
    # -----------------------------------------------------------------------

    @staticmethod
    def bestellhistorie(kunden_id: int) -> list:
        """Liefert die Bestellungen eines Kunden (neueste zuerst).

        TODO: Sobald `BestellungService` von Mohammed steht, hier
        delegieren — etwa:

            from services.bestellung_service import BestellungService
            return BestellungService.alle_fuer_kunde(kunden_id)

        Bis dahin gibt diese Methode eine leere Liste zurück, damit die
        Profil-Seite nicht crasht. Sie ist hier verfügbar, damit die UI
        einen stabilen Aufrufpunkt hat („alles, was den Kunden betrifft,
        läuft über `KundenService`") und sich später nichts umbenennen
        muss.
        """
        # Platzhalter, bis Mohammeds BestellungService verfügbar ist.
        return []