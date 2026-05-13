"""
AuthService — Pizzeria Sunshine
================================
Authentifizierung und Registrierung — die zentrale Stelle für alles
rund um Login, Passwort und Account-Anlage.

Es gibt zwei Login-Pfade:
  - Kunden loggen sich im Frontend ein und können bestellen.
  - Mitarbeiter loggen sich im Admin-Bereich ein und sehen je nach Rolle
    Bestellungen, Menüpflege, Auslieferungen (siehe `MitarbeiterRolle`).

Beide nutzen Email + Passwort, sind aber getrennte Tabellen — ein Kunde
ist kein Mitarbeiter und umgekehrt. Diese Trennung ist bewusst, damit
sich Berechtigungen und Datenmodell nicht vermischen.

Designentscheidungen:
  - **bcrypt für Passwort-Hashing.** bcrypt ist langsam by design (das
    ist gewollt — bremst Brute-Force-Angriffe aus) und enthält von Haus
    aus einen zufälligen Salt pro Passwort. Wir nutzen `passlib`, weil
    es das Hash-Format inklusive Algorithmus und Cost-Faktor in einen
    String packt — wir können später den Cost-Faktor anheben, ohne alte
    Hashes zu invalidieren.
  - **Email wird normalisiert (lowercase + strip)** bevor sie gespeichert
    oder gesucht wird. SQLite ist case-sensitive, und Nutzer tippen Mails
    mal mit grossem ersten Buchstaben („Max@…") und mal klein. Ohne
    Normalisierung wären das verschiedene Accounts.
  - **Login gibt `Optional[Kunde]` / `Optional[Mitarbeiter]` zurück.**
    `None` bedeutet „Email oder Passwort falsch" — wir unterscheiden
    bewusst NICHT, was von beidem falsch war (das wäre eine Info, die
    ein Angreifer beim Account-Probing ausnutzen könnte: „Email
    existiert" wäre eine Bestätigung).
  - **Deaktivierte Mitarbeiter** (`aktiv=False`) können sich nicht mehr
    einloggen — auch wenn ihre Email noch in der DB steht. Sonst wäre
    der Soft-Delete in `MitarbeiterDAO.deaktivieren` wirkungslos.
  - **Registrierung wirft `ValueError`** bei doppelter Email, nicht
    `None`. Beim Registrieren will die UI eine klare Fehlermeldung
    anzeigen können („Diese Email wird bereits verwendet"); beim Login
    halten wir uns bewusst bedeckt (siehe oben).
"""

from __future__ import annotations

from typing import Optional

from passlib.hash import bcrypt

from dao.kunden_dao import KundenDAO
from dao.mitarbeiter_dao import MitarbeiterDAO
from domain.models import Kunde, Mitarbeiter
from utils.db import get_session


class AuthService:
    """Service für Login, Registrierung und Passwort-Verwaltung."""

    # -----------------------------------------------------------------------
    # Passwort-Helfer (Hashing + Prüfung)
    # -----------------------------------------------------------------------

    @staticmethod
    def passwort_hashen(passwort: str) -> str:
        """Erzeugt einen bcrypt-Hash für ein Klartext-Passwort.

        Wird beim Registrieren eines Kunden oder beim Anlegen eines
        Mitarbeiters aufgerufen. Das Resultat wandert in das Feld
        `passwort_hash` der jeweiligen Tabelle — das Klartext-Passwort
        darf NIE in die DB.

        `bcrypt.hash` erzeugt automatisch einen zufälligen Salt, sodass
        zwei gleiche Passwörter unterschiedliche Hashes haben.
        """
        if not passwort:
            raise ValueError("Passwort darf nicht leer sein.")
        return bcrypt.hash(passwort)

    @staticmethod
    def passwort_pruefen(passwort: str, passwort_hash: str) -> bool:
        """Prüft, ob ein Klartext-Passwort zu einem gespeicherten Hash passt.

        Wird beim Login verwendet. `bcrypt.verify` ist konstant in der
        Laufzeit (was die Gross-/Kleinschreibung des Hashes angeht) und
        damit sicher gegen Timing-Angriffe.
        """
        if not passwort or not passwort_hash:
            return False
        try:
            return bcrypt.verify(passwort, passwort_hash)
        except ValueError:
            # `bcrypt.verify` wirft, wenn der gespeicherte Hash kein
            # gültiger bcrypt-Hash ist (z. B. korrupte DB-Daten oder
            # Klartext-Passwörter aus einer alten Version). Wir geben
            # dann einfach „falsch" zurück statt die App crashen zu lassen.
            return False

    # -----------------------------------------------------------------------
    # Helfer — Email-Normalisierung
    # -----------------------------------------------------------------------

    @staticmethod
    def _email_normalisieren(email: str) -> str:
        """Vereinheitlicht eine Email für Vergleich und Speicherung.

        Lowercase + Whitespace abschneiden. Eigene Methode, damit
        Registrierung und Login garantiert dieselbe Logik benutzen —
        sonst legt man einen Kunden mit „Max@Beispiel.ch" an und der
        Login mit „max@beispiel.ch" findet ihn nicht.
        """
        return email.strip().lower()

    # -----------------------------------------------------------------------
    # Registrierung (nur Kunden — Mitarbeiter werden im Admin angelegt)
    # -----------------------------------------------------------------------

    @staticmethod
    def registriere_kunde(
        *,
        vorname: str,
        nachname: str,
        email: str,
        passwort: str,
        telefon: Optional[str] = None,
    ) -> Kunde:
        """Legt einen neuen Kunden an.

        Schritte:
          1. Eingaben grob validieren (nicht leer).
          2. Email normalisieren.
          3. Prüfen, ob die Email schon vergeben ist — falls ja,
             `ValueError` werfen (UI zeigt das als „Email bereits
             registriert").
          4. Passwort hashen.
          5. Kunde anlegen.

        Keyword-only-Argumente: damit der Aufruf in der UI immer
        explizit benennt, was wo hingehört — bei sechs Strings wäre die
        positionale Variante ein Bug-Magnet.
        """
        # 1. Eingaben validieren — grob, die UI sollte vorher schon prüfen
        if not vorname.strip():
            raise ValueError("Vorname darf nicht leer sein.")
        if not nachname.strip():
            raise ValueError("Nachname darf nicht leer sein.")
        if not email.strip():
            raise ValueError("Email darf nicht leer sein.")
        if not passwort:
            raise ValueError("Passwort darf nicht leer sein.")

        # 2. Email normalisieren
        email_normalisiert = AuthService._email_normalisieren(email)

        # 3-5. Existenz prüfen + Anlegen, alles in einer Transaktion
        with get_session() as session:
            if KundenDAO.email_existiert(session, email_normalisiert):
                raise ValueError(
                    f"Email '{email_normalisiert}' ist bereits registriert."
                )

            kunde = Kunde(
                vorname=vorname.strip(),
                nachname=nachname.strip(),
                email=email_normalisiert,
                telefon=telefon.strip() if telefon else None,
                passwort_hash=AuthService.passwort_hashen(passwort),
            )
            return KundenDAO.create(session, kunde)

    # -----------------------------------------------------------------------
    # Login — Kunden
    # -----------------------------------------------------------------------

    @staticmethod
    def login_kunde(email: str, passwort: str) -> Optional[Kunde]:
        """Versucht, einen Kunden anzumelden.

        Rückgabe:
          - Kunde-Objekt, wenn Email existiert und Passwort stimmt.
          - `None`, wenn entweder die Email nicht existiert oder das
            Passwort falsch ist. Wir geben bewusst NICHT preis, welcher
            der beiden Fälle eingetreten ist (siehe Modul-Docstring).

        Die Page (`login_page.py`) prüft auf `None` und zeigt eine
        generische Meldung wie „Email oder Passwort falsch".
        """
        if not email or not passwort:
            return None

        email_normalisiert = AuthService._email_normalisieren(email)

        with get_session() as session:
            kunde = KundenDAO.finde_per_email(session, email_normalisiert)
            if kunde is None:
                return None
            if not AuthService.passwort_pruefen(passwort, kunde.passwort_hash):
                return None
            return kunde

    # -----------------------------------------------------------------------
    # Login — Mitarbeiter
    # -----------------------------------------------------------------------

    @staticmethod
    def login_mitarbeiter(email: str, passwort: str) -> Optional[Mitarbeiter]:
        """Versucht, einen Mitarbeiter anzumelden.

        Zusätzlich zum Email-/Passwort-Check muss der Mitarbeiter `aktiv`
        sein — deaktivierte Mitarbeiter (siehe
        `MitarbeiterDAO.deaktivieren`) können sich nicht mehr einloggen,
        auch wenn ihr Account noch in der DB steht.

        Rückgabe:
          - Mitarbeiter-Objekt, wenn alles passt.
          - `None`, sonst (Email unbekannt, Passwort falsch, oder
            Account deaktiviert). Auch hier: keine Unterscheidung nach
            aussen, damit Angreifer keine Hinweise bekommen.
        """
        if not email or not passwort:
            return None

        email_normalisiert = AuthService._email_normalisieren(email)

        with get_session() as session:
            mitarbeiter = MitarbeiterDAO.finde_per_email(
                session, email_normalisiert
            )
            if mitarbeiter is None:
                return None
            if not mitarbeiter.aktiv:
                return None
            if not AuthService.passwort_pruefen(
                passwort, mitarbeiter.passwort_hash
            ):
                return None
            return mitarbeiter

    # -----------------------------------------------------------------------
    # Passwort ändern
    # -----------------------------------------------------------------------

    @staticmethod
    def passwort_aendern_kunde(
        kunden_id: int, altes_passwort: str, neues_passwort: str
    ) -> bool:
        """Setzt das Passwort eines Kunden neu — nach Bestätigung des alten.

        Sicherheitsmassnahme: das alte Passwort muss korrekt sein, sonst
        könnte ein offen gelassener Browser-Tab missbraucht werden, um
        das Passwort zu wechseln und den Account zu übernehmen.

        Rückgabe:
          - True, wenn das Passwort gesetzt wurde.
          - False, wenn der Kunde nicht existiert oder das alte Passwort
            falsch war.

        Wirft `ValueError`, wenn das neue Passwort leer ist — das ist
        kein „Auth-Fehler", sondern eine Eingabe-Validierung.
        """
        if not neues_passwort:
            raise ValueError("Neues Passwort darf nicht leer sein.")

        with get_session() as session:
            kunde = KundenDAO.get_by_id(session, kunden_id)
            if kunde is None:
                return False
            if not AuthService.passwort_pruefen(
                altes_passwort, kunde.passwort_hash
            ):
                return False

            kunde.passwort_hash = AuthService.passwort_hashen(neues_passwort)
            KundenDAO.update(session, kunde)
            return True

    @staticmethod
    def passwort_aendern_mitarbeiter(
        mitarbeiter_id: int, altes_passwort: str, neues_passwort: str
    ) -> bool:
        """Setzt das Passwort eines Mitarbeiters neu — Logik analog zu
        `passwort_aendern_kunde`.

        Eigenständige Methode (statt Generic), damit der Aufruf-Ort
        explizit ist: „Kunde ändert Kundenpasswort" vs. „Mitarbeiter
        ändert Mitarbeiterpasswort" sind zwei verschiedene Use-Cases.
        """
        if not neues_passwort:
            raise ValueError("Neues Passwort darf nicht leer sein.")

        with get_session() as session:
            mitarbeiter = MitarbeiterDAO.get_by_id(session, mitarbeiter_id)
            if mitarbeiter is None:
                return False
            if not AuthService.passwort_pruefen(
                altes_passwort, mitarbeiter.passwort_hash
            ):
                return False

            mitarbeiter.passwort_hash = AuthService.passwort_hashen(
                neues_passwort
            )
            MitarbeiterDAO.update(session, mitarbeiter)
            return True