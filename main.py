import csv
from decimal import Decimal

def lade_menu(dateiname):
    """Lädt das Menü aus einer CSV-Datei und gibt eine Liste von Dictionaries zurück."""
    menu = []
    try:
        with open(dateiname, mode="r", encoding="utf-8") as csvfile:        #öffnet CSV Datei im Lesemodus, zeigt korrekte Umlaute durch UTF-8 an
            reader = csv.reader(csvfile, delimiter=";")
            header = next(reader)

            # Header-Namen in Kleinbuchstaben für flexible Erkennung
            header = [h.strip().lower() for h in header]

            # Erwartete Spaltennamen (tolerant gegenüber kleinen Abweichungen)
            id_index = header.index("id") if "id" in header else 0
            name_index = header.index("name") if "name" in header else 1
            preis_index = header.index("preis") if "preis" in header else 2

            for row in reader:      #Iteriert nun Zeile für Zeile damit es nicht nur den header der CSV anzeigt
                try:
                    item = {
                        "id": int(row[id_index]),
                        "name": row[name_index],
                        "preis": Decimal(row[preis_index].replace(",", "."))
                    }
                    menu.append(item)           #speichert item in menu Dictionary
                except Exception:
                    continue  # überspringt fehlerhafte Zeilen
        return menu

    except FileNotFoundError:
        print("Menüdatei wurde nicht gefunden.")
        return []
    except Exception as e:
        print(f"Fehler beim Laden des Menüs: {e}")
        return []

def zeige_menu(menu):
    """Zeigt das Menü formatiert an."""
    print("\n--- Menü Pizzeria Sunshine ---")
    for item in menu:
        print(f"{item['id']:>2}. {item['name']:<25} {item['preis']:.2f} €")
    print("--------------------------------")


def finde_artikel(menu, artikel_id):
    """Sucht einen Artikel anhand seiner ID."""
    for item in menu:
        if item["id"] == artikel_id:
            return item
    return None


def artikel_hinzufuegen(menu, warenkorb):
    """Fügt einen Artikel aus dem Menü dem Warenkorb hinzu."""
    try:
        artikel_id = int(input("Bitte Artikel-ID eingeben: "))
        artikel = finde_artikel(menu, artikel_id)
        if artikel is None:
            print("Ungültige Artikel-ID.")
            return

        menge = int(input(f"Wieviele '{artikel['name']}' möchten Sie? "))
        if menge <= 0:
            print("Ungültige Menge.")
            return

        if artikel_id in warenkorb:
            warenkorb[artikel_id]["menge"] += menge
        else:
            warenkorb[artikel_id] = {
                "name": artikel["name"],
                "preis": artikel["preis"],
                "menge": menge
            }

        print(f"{menge}x {artikel['name']} zum Warenkorb hinzugefügt.")

    except ValueError:
        print("Bitte nur ganze Zahlen eingeben.")


def zeige_warenkorb(warenkorb):
    """Zeigt alle Artikel im Warenkorb an."""
    if not warenkorb:
        print("\nIhr Warenkorb ist leer.")
        return

    print("\n--- Warenkorb ---")
    gesamt = Decimal("0.00")
    for item in warenkorb.values():
        zwischensumme = item["preis"] * item["menge"]
        gesamt += zwischensumme
        print(f"{item['menge']}x {item['name']:<25} = {zwischensumme:.2f} €")
    print(f"------------------------------\nGesamt: {gesamt:.2f} €\n")


if __name__ == "__main__":
    menu = lade_menu("Menü Pizzeria.csv")
    warenkorb = {}

    if not menu:
        exit()

    while True:
        print("\n1. Menü anzeigen")
        print("2. Artikel hinzufügen")
        print("3. Warenkorb anzeigen")
        print("4. Beenden")

        auswahl = input("Bitte wählen: ")

        if auswahl == "1":
            zeige_menu(menu)
        elif auswahl == "2":
            artikel_hinzufuegen(menu, warenkorb)
        elif auswahl == "3":
            zeige_warenkorb(warenkorb)
        elif auswahl == "4":
            print("Programm beendet.")
            break
        else:
            print("Ungültige Auswahl.")

# ============================================================================
# WUNSCHPIZZA.PY - KLASSE ZUM ERSTELLEN VON EIGENEN PIZZAS
# ============================================================================

# NOTIZ: Diese Klasse ermöglicht es Kunden, ihre eigene Pizza zusammenzustellen
# indem sie einzelne Zutaten auswählen und kombinieren.

class WunschPizza:
    """
    Diese Klasse verwaltet eine selbst zusammengestellte Pizza.
    Der Kunde wählt Zutaten aus und zahlt für jede Zutat extra.
    """
    
    # NOTIZ: __init__ ist der Konstruktor - wird aufgerufen, wenn ein neues
    # WunschPizza-Objekt erstellt wird
    def __init__(self):
        # NOTIZ: Eine leere Liste für die ausgewählten Zutaten
        self.zutaten = []
        
        # NOTIZ: Basis-Preis für eine leere Pizza (ohne Zutaten)
        self.basis_preis = 12.00
        
        # NOTIZ: Jede zusätzliche Zutat kostet 1.50 CHF
        self.preis_pro_zutat = 1.50
    
    
    def zutat_hinzufuegen(self, zutat: str):
        """
        NOTIZ: Diese Methode fügt eine Zutat zur Pizza hinzu.
        
        Parameter:
        - zutat: Der Name der Zutat (z.B. "Mozzarella")
        
        NOTIZ: Wir überprüfen zuerst, ob die Zutat bereits hinzugefügt wurde,
        um Duplikate zu vermeiden.
        """
        
        # NOTIZ: "if zutat not in self.zutaten:" prüft, ob die Zutat NICHT
        # bereits in der Liste vorhanden ist
        if zutat not in self.zutaten:
            # NOTIZ: .append() fügt ein Element am Ende der Liste hinzu
            self.zutaten.append(zutat)
            print(f"OK {zutat} hinzugefuegt (+CHF {self.preis_pro_zutat:.2f})")
        else:
            # NOTIZ: Falls die Zutat bereits vorhanden ist, geben wir eine
            # Warnung aus
            print(f"WARNUNG {zutat} ist bereits ausgewaehlt!")
    
    
    def zutat_entfernen(self, zutat: str):
        """
        NOTIZ: Diese Methode entfernt eine Zutat von der Pizza.
        
        Parameter:
        - zutat: Der Name der Zutat, die entfernt werden soll
        """
        
        # NOTIZ: Wir überprüfen, ob die Zutat in der Liste vorhanden ist
        if zutat in self.zutaten:
            # NOTIZ: .remove() entfernt das erste Vorkommen des Elements
            self.zutaten.remove(zutat)
            print(f"OK {zutat} entfernt")
        else:
            # NOTIZ: Falls die Zutat nicht vorhanden ist, geben wir eine
            # Warnung aus
            print(f"WARNUNG {zutat} ist nicht ausgewaehlt!")
    
    
    def preis_berechnen(self) -> float:
        """
        NOTIZ: Diese Methode berechnet den Gesamtpreis der Wunschpizza.
        
        Formel: Basis-Preis + (Anzahl Zutaten x Preis pro Zutat)
        Beispiel: 12.00 + (3 x 1.50) = 16.50 CHF
        
        Rückgabewert:
        - float: Der Gesamtpreis der Pizza
        
        NOTIZ: "-> float" bedeutet, dass diese Methode einen float-Wert
        zurückgibt
        """
        
        # NOTIZ: len(self.zutaten) gibt die Anzahl der Zutaten zurück
        anzahl_zutaten = len(self.zutaten)
        
        # NOTIZ: Wir multiplizieren die Anzahl mit dem Preis pro Zutat
        # und addieren den Basis-Preis
        gesamtpreis = self.basis_preis + (anzahl_zutaten * self.preis_pro_zutat)
        
        return gesamtpreis
    
    
    def pizza_anzeigen(self):
        """
        NOTIZ: Diese Methode zeigt die zusammengestellte Pizza in einem
        schönen Format an.
        """
        
        print("\n" + "="*60)
        print("DEINE WUNSCHPIZZA")
        print("="*60)
        
        # NOTIZ: Wir zeigen zuerst den Basis-Preis an
        print(f"Basis-Pizza: CHF {self.basis_preis:.2f}")
        
        # NOTIZ: Wir überprüfen, ob überhaupt Zutaten ausgewählt wurden
        if not self.zutaten:
            # NOTIZ: "not self.zutaten" ist True, wenn die Liste leer ist
            print("Zutaten: Keine ausgewaehlt")
        else:
            # NOTIZ: Wenn Zutaten vorhanden sind, zeigen wir sie alle an
            print(f"Zutaten ({len(self.zutaten)} Stueck):")
            
            # NOTIZ: Wir iterieren durch alle Zutaten mit einer for-Schleife
            for zutat in self.zutaten:
                # NOTIZ: Jede Zutat wird mit einem Bindestrich angezeigt
                print(f"  - {zutat} (+CHF {self.preis_pro_zutat:.2f})")
        
        # NOTIZ: Trennlinie für bessere Lesbarkeit
        print("-"*60)
        
        # NOTIZ: Wir rufen die preis_berechnen()-Methode auf und zeigen
        # den Gesamtpreis an
        print(f"Gesamtpreis: CHF {self.preis_berechnen():.2f}")
        print("="*60 + "\n")
    
    
    def ist_valid(self) -> bool:
        """
        NOTIZ: Diese Hilfsmethode prüft, ob die Pizza gültig ist
        (mindestens eine Zutat hat).
        
        Rückgabewert:
        - bool: True wenn mindestens eine Zutat vorhanden ist, sonst False
        """
        
        # NOTIZ: Wir geben True zurück, wenn die Liste nicht leer ist
        return len(self.zutaten) > 0
    

# ============================================================================
# BESTELLUNGEN.PY - FUNKTIONEN FUER PIZZA-, GETRAENK- UND WUNSCHPIZZA-BESTELLUNGEN
# ============================================================================

# NOTIZ: Wir importieren die notwendigen Module und Klassen von anderen Dateien
from warenkorb import PIZZEN, GETRAENKE, ZUTATEN, Warenkorb
from wunschpizza import WunschPizza


# ============================================================================
# FUNKTION 1: PIZZEN BESTELLEN
# ============================================================================

def pizza_bestellen(warenkorb: Warenkorb):
    """
    NOTIZ: Diese Funktion ermöglicht dem Kunden, eine vordefinierte Pizza
    aus dem Menü zu bestellen.
    
    Parameter:
    - warenkorb: Das Warenkorb-Objekt, in das die Pizza hinzugefügt wird
    
    NOTIZ: "warenkorb: Warenkorb" bedeutet, dass dieser Parameter vom Typ
    Warenkorb sein muss (Type Hint)
    """
    
    # NOTIZ: Zuerst zeigen wir alle verfügbaren Pizzen an
    print("\n" + "="*60)
    print("VERFUEGBARE PIZZEN")
    print("="*60)
    
    # NOTIZ: Wir iterieren durch das PIZZEN-Dictionary
    # .items() gibt uns sowohl den Schlüssel (pizza_id) als auch den Wert
    for pizza_id, pizza_info in PIZZEN.items():
        # NOTIZ: pizza_info ist ein Dictionary mit "name" und "preis"
        name = pizza_info["name"]
        preis = pizza_info["preis"]
        
        # NOTIZ: Wir formatieren die Ausgabe schön mit Abständen
        print(f"{pizza_id:2d}. {name:<35} CHF {preis:>6.2f}")
    
    print("="*60 + "\n")
    
    # NOTIZ: try-except fängt Fehler auf (z.B. wenn der Benutzer keine Zahl eingibt)
    try:
        # NOTIZ: Wir fragen den Benutzer, welche Pizza er möchte
        pizza_id = int(input("Welche Pizza moechtest du? (ID eingeben): "))
        
        # NOTIZ: Wir überprüfen, ob die eingegebene ID gültig ist
        # "in PIZZEN" prüft, ob die ID als Schlüssel im Dictionary existiert
        if pizza_id not in PIZZEN:
            print("WARNUNG Diese Pizza existiert nicht!")
            return  # NOTIZ: return beendet die Funktion
        
        # NOTIZ: Wir fragen nach der Menge
        menge = int(input("Wie viele moechtest du? "))
        
        # NOTIZ: Wir überprüfen, ob die Menge sinnvoll ist (mindestens 1)
        if menge <= 0:
            print("WARNUNG Die Menge muss mindestens 1 sein!")
            return
        
        # NOTIZ: Wir holen die Pizza-Informationen aus dem Dictionary
        pizza_info = PIZZEN[pizza_id]
        name = pizza_info["name"]
        preis = pizza_info["preis"]
        
        # NOTIZ: Wir fügen die Pizza zum Warenkorb hinzu
        warenkorb.artikel_hinzufuegen(pizza_id, name, preis, menge)
    
    except ValueError:
        # NOTIZ: ValueError tritt auf, wenn int() keine gültige Zahl bekommt
        print("WARNUNG Bitte gib eine gueltige Zahl ein!")


# ============================================================================
# FUNKTION 2: GETRAENKE BESTELLEN
# ============================================================================

def getraenk_bestellen(warenkorb: Warenkorb):
    """
    NOTIZ: Diese Funktion ist sehr ähnlich wie pizza_bestellen(),
    aber für Getränke.
    
    Parameter:
    - warenkorb: Das Warenkorb-Objekt
    """
    
    # NOTIZ: Wir zeigen alle verfügbaren Getränke an
    print("\n" + "="*60)
    print("VERFUEGBARE GETRAENKE")
    print("="*60)
    
    # NOTIZ: Wir iterieren durch das GETRAENKE-Dictionary
    for getraenk_id, getraenk_info in GETRAENKE.items():
        name = getraenk_info["name"]
        preis = getraenk_info["preis"]
        print(f"{getraenk_id:2d}. {name:<35} CHF {preis:>6.2f}")
    
    print("="*60 + "\n")
    
    try:
        # NOTIZ: Wir fragen nach der Getränk-ID
        getraenk_id = int(input("Welches Getraenk moechtest du? (ID eingeben): "))
        
        # NOTIZ: Wir überprüfen, ob die ID gültig ist
        if getraenk_id not in GETRAENKE:
            print("WARNUNG Dieses Getraenk existiert nicht!")
            return
        
        # NOTIZ: Wir fragen nach der Menge
        menge = int(input("Wie viele moechtest du? "))
        
        # NOTIZ: Wir überprüfen die Menge
        if menge <= 0:
            print("WARNUNG Die Menge muss mindestens 1 sein!")
            return
        
        # NOTIZ: Wir holen die Getränk-Informationen
        getraenk_info = GETRAENKE[getraenk_id]
        name = getraenk_info["name"]
        preis = getraenk_info["preis"]
        
        # NOTIZ: Wir fügen das Getränk zum Warenkorb hinzu
        warenkorb.artikel_hinzufuegen(getraenk_id, name, preis, menge)
    
    except ValueError:
        print("WARNUNG Bitte gib eine gueltige Zahl ein!")


# ============================================================================
# FUNKTION 3: WUNSCHPIZZA ERSTELLEN UND BESTELLEN
# ============================================================================

def wunschpizza_erstellen(warenkorb: Warenkorb):
    """
    NOTIZ: Diese Funktion ist das Herzstück von Person 2!
    Sie ermöglicht dem Kunden, seine eigene Pizza zusammenzustellen.
    
    Parameter:
    - warenkorb: Das Warenkorb-Objekt
    
    Ablauf:
    1. Ein neues WunschPizza-Objekt erstellen
    2. Zutaten anzeigen
    3. Benutzer Zutaten auswählen lassen
    4. Pizza anzeigen
    5. Bestätigung einholen
    6. Menge fragen
    7. Zum Warenkorb hinzufügen
    """
    
    # NOTIZ: Wir erstellen ein neues WunschPizza-Objekt
    pizza = WunschPizza()
    
    # NOTIZ: Wir zeigen die Anleitung an
    print("\n" + "="*60)
    print("WUNSCHPIZZA ERSTELLEN")
    print("="*60)
    print("Verfuegbare Zutaten:")
    
    # NOTIZ: Wir zeigen alle Zutaten mit Nummern an
    # enumerate(ZUTATEN, 1) nummeriert die Zutaten ab 1 (nicht ab 0)
    for idx, zutat in enumerate(ZUTATEN, 1):
        print(f"{idx:2d}. {zutat}")
    
    print("="*60)
    print("Gib die Nummern der Zutaten ein (durch Komma getrennt)")
    print("Beispiel: 1,3,5 (fuer Mozzarella, Basilikum, Pilze)")
    print("Oder gib 'fertig' ein, wenn du fertig bist")
    print("="*60 + "\n")
    
    try:
        # NOTIZ: Wir starten eine Endlosschleife (while True)
        # Diese läuft solange, bis der Benutzer "fertig" eingibt
        while True:
            # NOTIZ: Wir fragen den Benutzer nach Zutaten
            # .strip() entfernt Leerzeichen am Anfang/Ende
            # .lower() wandelt alles in Kleinbuchstaben um
            eingabe = input("Zutaten eingeben: ").strip().lower()
            
            # NOTIZ: Wir überprüfen, ob der Benutzer "fertig" eingegeben hat
            if eingabe == "fertig":
                # NOTIZ: Wir prüfen, ob mindestens eine Zutat ausgewählt wurde
                if not pizza.ist_valid():
                    print("WARNUNG Bitte waehle mindestens eine Zutat!")
                    continue  # NOTIZ: continue springt zum Anfang der Schleife
                
                # NOTIZ: Wenn alles ok ist, brechen wir aus der Schleife aus
                break
            
            # NOTIZ: Wir teilen die Eingabe bei Kommas auf
            # z.B. "1,3,5" wird zu ["1", "3", "5"]
            nummern = [int(x.strip()) for x in eingabe.split(",")]
            
            # NOTIZ: Für jede eingegebene Nummer...
            for nummer in nummern:
                # NOTIZ: Wir überprüfen, ob die Nummer gültig ist
                # Die Nummern müssen zwischen 1 und len(ZUTATEN) liegen
                if 1 <= nummer <= len(ZUTATEN):
                    # NOTIZ: ZUTATEN[nummer - 1] weil Listen bei 0 anfangen
                    # aber wir bei 1 nummeriert haben
                    zutat = ZUTATEN[nummer - 1]
                    pizza.zutat_hinzufuegen(zutat)
                else:
                    print(f"WARNUNG Zutat {nummer} existiert nicht!")
    
    except ValueError:
        # NOTIZ: ValueError tritt auf, wenn die Eingabe keine Zahl ist
        print("WARNUNG Bitte gib gueltige Nummern ein!")
        return
    
    # NOTIZ: Nach der Zutatenwahl zeigen wir die Pizza an
    pizza.pizza_anzeigen()
    
    # NOTIZ: Wir fragen den Benutzer, ob er die Pizza bestellen möchte
    bestaetigung = input("Moechtest du diese Pizza bestellen? (ja/nein): ").strip().lower()
    
    # NOTIZ: Wir überprüfen die Antwort
    if bestaetigung == "ja":
        try:
            # NOTIZ: Wir fragen nach der Menge
            menge = int(input("Wie viele Stueck? "))
            
            # NOTIZ: Wir überprüfen, ob die Menge gültig ist
            if menge > 0:
                # NOTIZ: Wir erstellen einen beschreibenden Namen für die Pizza
                # z.B. "Wunschpizza mit Mozzarella, Tomaten, Basilikum"
                zutaten_text = ", ".join(pizza.zutaten)
                name = f"Wunschpizza mit {zutaten_text}"
                
                # NOTIZ: Wir fügen die Pizza zum Warenkorb hinzu
                # ID 999 ist eine spezielle ID für Wunschpizzas
                warenkorb.artikel_hinzufuegen(
                    999,
                    name,
                    pizza.preis_berechnen(),
                    menge
                )
            else:
                print("WARNUNG Die Menge muss mindestens 1 sein!")
        
        except ValueError:
            print("WARNUNG Bitte gib eine gueltige Zahl ein!")
    else:
        # NOTIZ: Falls der Benutzer "nein" sagt, wird die Pizza nicht hinzugefügt
        print("Die Pizza wurde nicht hinzugefuegt.")


# ============================================================================
# FUNKTION 4: QUITTUNG ERSTELLEN
# ============================================================================

def quittung_erstellen(warenkorb: Warenkorb):
    """
    NOTIZ: Diese Funktion erstellt eine Quittung und beendet die Bestellung.
    
    Parameter:
    - warenkorb: Das Warenkorb-Objekt
    
    Rückgabewert:
    - bool: True wenn die Bestellung erfolgreich war, sonst False
    
    NOTIZ: Diese Funktion gibt True oder False zurück, damit das Hauptprogramm
    weiß, ob es beendet werden soll.
    """
    
    # NOTIZ: Wir überprüfen, ob der Warenkorb leer ist
    if not warenkorb.artikel:
        print("\nWARNUNG Der Warenkorb ist leer!")
        print("Es kann keine Bestellung aufgegeben werden.")
        return False  # NOTIZ: Wir geben False zurück
    
    # NOTIZ: Wir importieren datetime, um das aktuelle Datum/Uhrzeit zu bekommen
    from datetime import datetime
    jetzt = datetime.now()
    
    # NOTIZ: Wir zeigen die Quittung an
    print("\n" + "="*60)
    print("QUITTUNG - PIZZERIA SUNSHINE")
    print("="*60)
    print(f"Datum: {jetzt.strftime('%d.%m.%Y')}")
    print(f"Uhrzeit: {jetzt.strftime('%H:%M:%S')}")
    print("="*60)
    
    # NOTIZ: Wir zeigen alle Artikel aus dem Warenkorb an
    for artikel in warenkorb.artikel:
        name = artikel["name"]
        menge = artikel["menge"]
        preis = artikel["preis"]
        gesamtpreis = artikel["gesamtpreis"]
        
        print(f"{name:<35} {menge:>2}x CHF {preis:>6.2f} = CHF {gesamtpreis:>7.2f}")
    
    # NOTIZ: Trennlinie und Gesamtpreis
    print("-"*60)
    gesamtpreis = warenkorb.gesamtpreis_berechnen()
    print(f"{'GESAMTPREIS':<35} {'':>2}  {'':>6}   CHF {gesamtpreis:>7.2f}")
    print("="*60)
    
    # NOTIZ: Abschlussnachrichten
    print("\nOK Vielen Dank fuer deine Bestellung!")
    print("OK Deine Bestellung wird in ca. 30-45 Minuten geliefert.")
    print("OK Guten Appetit!\n")
    
    # NOTIZ: Wir geben True zurück, um anzuzeigen, dass alles ok war
    return True