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
    aus einen zufälligen Salt pro Passwort. Das Hash-Format enthält
    Algorithmus + Cost-Faktor + Salt + Hash in einem einzigen String,
    sodass wir später den Cost-Faktor erhöhen können, ohne alte Hashes
    zu invalidieren.
  - **bcrypt-Limit von 72 Bytes:** Die bcrypt-Bibliothek lehnt Passwörter
    über 72 Bytes ab. Wir kürzen daher in `passwort_hashen` auf 72 Bytes
    — bei realistischen Passwörtern (auch langen Passphrasen) tritt das
    nie ein, aber so vermeiden wir einen harten Crash bei Extremfällen.
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

import bcrypt

from dao.kunden_dao import KundenDAO
from dao.mitarbeiter_dao import MitarbeiterDAO
from domain.models import Kunde, Mitarbeiter
from utils.db import get_session


class AuthService:
    """Service für Login, Registrierung und Passwort-Verwaltung."""

    # -----------------------------------------------------------------------
    # Passwort-Helfer (Hashing + Prüfung)
    # -----------------------------------------------------------------------

    # Maximale Passwortlänge in Bytes, die bcrypt unterstützt.
    # Längere Passwörter werden vor dem Hashing abgeschnitten — dieselbe
    # Längenbegrenzung muss dann auch beim Prüfen gelten, sonst stimmen
    # Hashes nicht überein.
    _MAX_PASSWORT_BYTES = 72

    @staticmethod
    def _passwort_zu_bytes(passwort: str) -> bytes:
        """Wandelt das Passwort in UTF-8-Bytes um und kürzt auf 72 Bytes.

        bcrypt arbeitet auf Bytes, nicht auf Strings, und akzeptiert
        maximal 72 Bytes (alle weiteren werden ohnehin ignoriert). Wir
        kürzen explizit, damit das Verhalten zwischen `passwort_hashen`
        und `passwort_pruefen` konsistent ist und keine Warnungen kommen.
        """
        return passwort.encode("utf-8")[: AuthService._MAX_PASSWORT_BYTES]

    @staticmethod
    def passwort_hashen(passwort: str) -> str:
        """Erzeugt einen bcrypt-Hash für ein Klartext-Passwort.

        Wird beim Registrieren eines Kunden oder beim Anlegen eines
        Mitarbeiters aufgerufen. Das Resultat wandert in das Feld
        `passwort_hash` der jeweiligen Tabelle — das Klartext-Passwort
        darf NIE in die DB.

        `bcrypt.gensalt()` erzeugt automatisch einen zufälligen Salt,
        sodass zwei gleiche Passwörter unterschiedliche Hashes haben.
        Der Rückgabe-String enthält Algorithmus + Cost + Salt + Hash,
        damit `checkpw` später weiss, wie er das Klartext-Passwort
        hashen muss, um es zu vergleichen.
        """
        if not passwort:
            raise ValueError("Passwort darf nicht leer sein.")
        hash_bytes = bcrypt.hashpw(
            AuthService._passwort_zu_bytes(passwort), bcrypt.gensalt()
        )
        return hash_bytes.decode("utf-8")

    @staticmethod
    def passwort_pruefen(passwort: str, passwort_hash: str) -> bool:
        """Prüft, ob ein Klartext-Passwort zu einem gespeicherten Hash passt.

        Wird beim Login verwendet. `bcrypt.checkpw` ist konstant in der
        Laufzeit und damit sicher gegen Timing-Angriffe (ein Angreifer
        kann anhand der Antwortzeit nicht erraten, wie viele Zeichen
        seiner Eingabe stimmen).
        """
        if not passwort or not passwort_hash:
            return False
        try:
            return bcrypt.checkpw(
                AuthService._passwort_zu_bytes(passwort),
                passwort_hash.encode("utf-8"),
            )
        except (ValueError, TypeError):
            # `bcrypt.checkpw` wirft, wenn der gespeicherte Hash kein
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
                raise ValueError("Altes Passwort ist falsch.")

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
                raise ValueError("Altes Passwort ist falsch.")

            mitarbeiter.passwort_hash = AuthService.passwort_hashen(
                neues_passwort
            )
            MitarbeiterDAO.update(session, mitarbeiter)
            return True
        
        # -------------------------------------------------------------------
    # Session-Verwaltung (NiceGUI app.storage.user)
    # -------------------------------------------------------------------
    # Wir speichern bewusst NUR die ID in der Session, nicht das ganze
    # ORM-Objekt — Cookies sind klein, und Objekte werden bei DB-Aenderungen
    # sonst stale. Beim Zugriff wird der User frisch aus der DB geladen.
    #
    # `from nicegui import app` passiert lokal in jeder Methode, damit die
    # Tests AuthService importieren koennen, ohne dass NiceGUI laufen muss.

    _SESSION_KEY_KUNDEN_ID = "kunden_id"
    _SESSION_KEY_MITARBEITER_ID = "mitarbeiter_id"

    @staticmethod
    def aktuellen_kunden_in_session_setzen(kunde: Kunde) -> None:
        """Speichert die Kunden-ID in der NiceGUI-Session."""
        from nicegui import app
        app.storage.user[AuthService._SESSION_KEY_KUNDEN_ID] = kunde.id
        # Falls vorher ein Mitarbeiter eingeloggt war: rauswerfen
        app.storage.user.pop(AuthService._SESSION_KEY_MITARBEITER_ID, None)

    @staticmethod
    def aktuellen_mitarbeiter_in_session_setzen(mitarbeiter: Mitarbeiter) -> None:
        """Speichert die Mitarbeiter-ID in der NiceGUI-Session."""
        from nicegui import app
        app.storage.user[AuthService._SESSION_KEY_MITARBEITER_ID] = mitarbeiter.id
        app.storage.user.pop(AuthService._SESSION_KEY_KUNDEN_ID, None)

    @staticmethod
    def aktueller_kunde() -> Optional[Kunde]:
        """Laedt den aktuell eingeloggten Kunden frisch aus der DB."""
        from nicegui import app
        kunden_id = app.storage.user.get(AuthService._SESSION_KEY_KUNDEN_ID)
        if kunden_id is None:
            return None
        with get_session() as session:
            return KundenDAO.get_by_id(session, kunden_id)

    @staticmethod
    def aktueller_mitarbeiter() -> Optional[Mitarbeiter]:
        """Laedt den aktuell eingeloggten Mitarbeiter frisch aus der DB."""
        from nicegui import app
        mitarbeiter_id = app.storage.user.get(AuthService._SESSION_KEY_MITARBEITER_ID)
        if mitarbeiter_id is None:
            return None
        with get_session() as session:
            return MitarbeiterDAO.get_by_id(session, mitarbeiter_id)

    @staticmethod
    def ist_eingeloggt() -> bool:
        """True, wenn ein Kunde ODER ein Mitarbeiter eingeloggt ist."""
        from nicegui import app
        return (
            app.storage.user.get(AuthService._SESSION_KEY_KUNDEN_ID) is not None
            or app.storage.user.get(AuthService._SESSION_KEY_MITARBEITER_ID) is not None
        )

    @staticmethod
    def ausloggen() -> None:
        """Entfernt Kunden- und Mitarbeiter-Session."""
        from nicegui import app
        app.storage.user.pop(AuthService._SESSION_KEY_KUNDEN_ID, None)
        app.storage.user.pop(AuthService._SESSION_KEY_MITARBEITER_ID, None)