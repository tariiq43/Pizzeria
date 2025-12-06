# Benötigte Module importieren (csv, dezimalzahlen, datum/zeit)
import csv
from decimal import Decimal
import os
from datetime import datetime
from artikel_einlesen import lade_menu

# Speichert die Bestellung dauerhaft in der Datei "orders.csv"
def bestellung_in_csv_speichern(warenkorb, order_id, jetzt, gesamtpreis, dateiname="orders.csv"):
    """
    Speichert die Bestellung in einer CSV-Datei.
    Jede Zeile entspricht einem Artikel der Bestellung.
    """
    #Prüfen, ob die Datei bereits existiert
    datei_existiert = os.path.isfile(dateiname)

    with open(dateiname, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")


        if not datei_existiert:
            writer.writerow([
                "order_id", "datum", "uhrzeit",
                "artikel_id", "artikel_name", "menge",
                "einzelpreis", "artikel_gesamtpreis",
                "bestellung_gesamtpreis"
            ])

        for artikel_id, artikel in warenkorb.items():
            artikel_gesamtpreis = artikel["preis"] * artikel["menge"]

            writer.writerow([
                order_id,
                jetzt.strftime("%d.%m.%Y"),
                jetzt.strftime("%H:%M:%S"),
                artikel_id,
                artikel["name"],
                artikel["menge"],
                f"{artikel['preis']:.2f}",
                f"{artikel_gesamtpreis:.2f}",
                f"{gesamtpreis:.2f}"
            ])

#Erzeugt eine Quittung als TXT-Datei zur Bestellung
def quittung_als_textdatei_speichern(warenkorb, order_id, jetzt, gesamtpreis):
    """
    Speichert die Quittung als TXT-Datei.
    """
    
    #Dateiname enthält die Bestellnummer(order_id)
    dateiname = f"quittung_{order_id}.txt"

    with open(dateiname, mode="w", encoding="utf-8") as f:
        f.write("QUITTUNG - PIZZERIA SUNSHINE\n")
        f.write("=" * 60 + "\n")
        f.write(f"Bestellnummer: {order_id}\n")
        f.write(f"Datum: {jetzt.strftime('%d.%m.%Y')}\n")
        f.write(f"Uhrzeit: {jetzt.strftime('%H:%M:%S')}\n")
        f.write("=" * 60 + "\n")


        # Alle Artikel aus dem Warenkorb in die Quittung übertragen
        for artikel_id, artikel in warenkorb.items():
            artikel_gesamtpreis = artikel["preis"] * artikel["menge"]

            f.write(
                f"{artikel['name']:<35} {artikel['menge']:>2}x "
            )
            f.write(
                f"CHF {artikel['preis']:>6.2f} = CHF {artikel_gesamtpreis:>7.2f}\n"
            )

        f.write("-" * 60 + "\n")
        f.write(f"{'GESAMTPREIS':<35} CHF {gesamtpreis:>7.2f}\n")
        f.write("=" * 60 + "\n")
        f.write("Vielen Dank für Ihre Bestellung!\n")

# Gibt das Mneü formatiert im Terminal aus
def zeige_menu(menu):
    """Zeigt das Menü formatiert an."""
    print("\n--- Menü Pizzeria Sunshine ---")
    for item in menu:
        print(f"{item['id']:>2}. {item['name']:<25} {item['preis']:.2f} €")         
    print("--------------------------------")

# Sucht in der Menü-Liste nach einer Artikel-ID und gibt den Artikel
def finde_artikel(menu, artikel_id):
    """Sucht einen Artikel anhand seiner ID."""
    for item in menu:
        if item["id"] == artikel_id:
            return item
    return None

# Ermöglicht dem Benutzer, einen Artikel aus dem Menü zum Warenkorb hinzuzufügen
def artikel_hinzufuegen(menu, warenkorb):
    """Fügt einen Artikel aus dem Menü dem Warenkorb hinzu."""
    try:
        artikel_id = int(input("Bitte Artikel-ID eingeben: "))
        artikel = finde_artikel(menu, artikel_id)
        if artikel is None:
            try:
                artikel = int(artikel)
            except ValueError as e:
                print("Keine Zahl eingegeben")
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

# Zeigt alle Artikel im Warenkorb mit Mengen und Preisen an
def zeige_warenkorb(warenkorb):
    """Zeigt alle Artikel im Warenkorb an."""
    if not warenkorb:
        print("\nIhr Warenkorb ist leer.")
        return

# Zwischensumme pro Artikel berechnen (Preis * Menge)
    print("\n--- Warenkorb ---")
    gesamt = Decimal("0.00")
    for item in warenkorb.values():
        zwischensumme = item["preis"] * item["menge"]
        gesamt += zwischensumme
        print(f"{item['menge']}x {item['name']:<25} = {zwischensumme:.2f} €")
    print(f"------------------------------\nGesamt: {gesamt:.2f} €\n")

# Gibt das Menü formatiert im Terminal aus
def zeige_menu(menu):
    """Zeigt das Menü formatiert an."""
    print("\n--- Menü Pizzeria Sunshine ---")
    for item in menu:
        print(f"{item['id']:>2}. {item['name']:<25} {item['preis']:.2f} €")         
    print("--------------------------------")

# Sucht einen Artikel im Mneü anhand sicherer ID
def finde_artikel(menu, artikel_id):
    """Sucht einen Artikel anhand seiner ID."""
    for item in menu:
        if item["id"] == artikel_id:
            return item
    return None

#Fügt einen Artikel aus dem Menü zum Warenkorb hinzu
def artikel_hinzufuegen(menu, warenkorb):
    """Fügt einen Artikel aus dem Menü dem Warenkorb hinzu."""
    try:
        artikel_id = int(input("Bitte Artikel-ID eingeben: ")) # Artikel mit dieser ID im Menü suchen
        artikel = finde_artikel(menu, artikel_id)
        
        if artikel is None:
            print("Ungültige Artikel-ID.") # Wenn keine passende ID gefunden wurde
            return

        menge = int(input(f"Wieviele '{artikel['name']}' möchten Sie? ")) # Menge prüfen 
        if menge <= 0:
            print("Ungültige Menge.")
            return

# Falls Artikel schon im Warenkorb, Menge erhöhen
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

# ============================================================================
# WUNSCHPIZZA KLASSE
# ============================================================================

class WunschPizza:
    """Verwaltet eine selbst zusammengestellte Pizza."""
    # Liste der ausgewählten Zutaten
    def __init__(self):
        self.zutaten = []
        self.basis_preis = 12.00
        self.preis_pro_zutat = 1.50
    
    # Fügt eine neue Zutat zur Pizza hinzu
    def zutat_hinzufuegen(self, zutat: str):
        """Fügt eine Zutat zur Pizza hinzu."""
        if zutat not in self.zutaten:
            self.zutaten.append(zutat)
            print(f"OK {zutat} hinzugefuegt (+CHF {self.preis_pro_zutat:.2f})")
        else:
            print(f"WARNUNG {zutat} ist bereits ausgewaehlt!")
   
    #Entfernt eine Zutat, falls sie vorhanen
    def zutat_entfernen(self, zutat: str):
        """Entfernt eine Zutat von der Pizza."""
        if zutat in self.zutaten:
            self.zutaten.remove(zutat)
            print(f"OK {zutat} entfernt")
        else:
            print(f"WARNUNG {zutat} ist nicht ausgewaehlt!")
    
    # Berechnet den Gesamtpreis der Wunschpizza
    def preis_berechnen(self) -> float:
        """Berechnet den Gesamtpreis der Wunschpizza."""
        return self.basis_preis + (len(self.zutaten) * self.preis_pro_zutat)
    
    #Zeigt die aktuell zusammengestellte Wunschpiza an
    def pizza_anzeigen(self):
        """Zeigt die zusammengestellte Pizza an."""
        print("\n" + "="*60)
        print("DEINE WUNSCHPIZZA")
        print("="*60)
        print(f"Basis-Pizza: CHF {self.basis_preis:.2f}")
        
        if not self.zutaten:
            print("Zutaten: Keine ausgewaehlt")
        else:
            print(f"Zutaten ({len(self.zutaten)} Stueck):")
            for zutat in self.zutaten:
                print(f"  - {zutat} (+CHF {self.preis_pro_zutat:.2f})")
        
        print("-"*60)
        print(f"Gesamtpreis: CHF {self.preis_berechnen():.2f}")
        print("="*60 + "\n")
    
    # Prüft, ob die Pizza gültig ist (mindestens 1 Zutat)
    def ist_valid(self) -> bool:
        """Prüft, ob die Pizza gültig ist (mindestens eine Zutat)."""
        return len(self.zutaten) > 0


# ============================================================================
# FUNKTION 3: WUNSCHPIZZA ERSTELLEN UND BESTELLEN
# ============================================================================

def wunschpizza_erstellen(menu, warenkorb):
    """Ermöglicht dem Kunden, seine eigene Pizza zusammenzustellen."""
    
    pizza = WunschPizza()
    
    # Liste aller verfügbaren Zutaten ausgeben
    zutaten_liste = ["Mozzarella", "Tomaten", "Basilikum", "Pilze", "Zwiebeln", 
                     "Paprika", "Oliven", "Schinken", "Peperoni", "Ananas"]
    
    print("\n" + "="*60)
    print("WUNSCHPIZZA ERSTELLEN")
    print("="*60)
    print("Verfuegbare Zutaten:")
    
    for idx, zutat in enumerate(zutaten_liste, 1):
        print(f"{idx:2d}. {zutat}")
    
    print("="*60)
    print("Gib die Nummern der Zutaten ein (durch Komma getrennt)")
    print("Beispiel: 1,3,5")
    print("Oder gib 'fertig' ein, wenn du fertig bist")
    print("="*60 + "\n")
    
    try:
        while True:
            eingabe = input("Zutaten eingeben: ").strip().lower()
            # Eingabe wird verarbeitet
            if eingabe == "fertig":
                if not pizza.ist_valid():
                    print("WARNUNG Bitte waehle mindestens eine Zutat!")
                    continue
                break
            
            try:
                nummern = [int(x.strip()) for x in eingabe.split(",")]
                # Benutzer hat mehrere Zutatennummern eingegeben
                for nummer in nummern:
                    if 1 <= nummer <= len(zutaten_liste):
                        zutat = zutaten_liste[nummer - 1]
                        pizza.zutat_hinzufuegen(zutat)
                    else:
                        print(f"WARNUNG Zutat {nummer} existiert nicht!")
            except ValueError:
                print("WARNUNG Bitte gib gueltige Nummern ein!")
                continue
    
    except Exception as e:
        print(f"Fehler: {e}")
        return
    
    pizza.pizza_anzeigen()
    
    bestaetigung = input("Moechtest du diese Pizza bestellen? (ja/nein): ").strip().lower()
    
    if bestaetigung == "ja":
        try:
            menge = int(input("Wie viele Stueck? "))
            
            if menge > 0:
                zutaten_text = ", ".join(pizza.zutaten)
                name = f"Wunschpizza mit {zutaten_text}"
                preis = pizza.preis_berechnen()
                
                # Feste ID für die Wunschpizza (damit andere IDs nicht überschrieben werden)
                pizza_id = 999
                if pizza_id in warenkorb:
                    warenkorb[pizza_id]["menge"] += menge
                else:
                    warenkorb[pizza_id] = {
                        "name": name,
                        "preis": Decimal(str(preis)),
                        "menge": menge
                    }
                
                print(f"OK {menge}x {name} zum Warenkorb hinzugefuegt.")
            else:
                print("WARNUNG Die Menge muss mindestens 1 sein!")
        
        except ValueError:
            print("WARNUNG Bitte gib eine gueltige Zahl ein!")
    else:
        print("Die Pizza wurde nicht hinzugefuegt.")


if __name__ == "__main__":
    menu = lade_menu("Menü Pizzeria.csv") # Menü wird aus der CSV-Datei geladen
    warenkorb = {}

    if not menu:
        exit()

# Hauptmenü anzeigen
    while True:
        print("\n1. Menü anzeigen")
        print("2. Artikel hinzufügen")
        print("3. Wunschpizza erstellen")
        print("4. Warenkorb anzeigen")
        print("5. Besellung abschliessen")
        print("6. Beenden")


        auswahl = input("Bitte wählen: ")

        if auswahl == "1":
            zeige_menu(menu)
        elif auswahl == "2":
            artikel_hinzufuegen(menu, warenkorb)
        elif auswahl == "3":
            wunschpizza_erstellen(menu, warenkorb)
        elif auswahl == "4":
            zeige_warenkorb(warenkorb)
        elif auswahl == "5":
            if not warenkorb:
                print("\nIhr Warenkorb ist leer, keien Bestellung möglich.")
                continue

            jetzt = datetime.now()
            order_id = int(jetzt.timestamp()) # Bestellnummer setzen (Zeitstempel)
            gesamtpreis = sum(
                artikel["preis"] * artikel["menge"]
                for artikel in warenkorb.values()
            )

            # Bestellung wir dauerhaft gespeichert
            bestellung_in_csv_speichern(warenkorb, order_id, jetzt, gesamtpreis)
            # Guittung wird als TXT erzeugt
            quittung_als_textdatei_speichern(warenkorb, order_id, jetzt,gesamtpreis)

            print("\nBestellung gespeichert und Quittung erstellt.\n")
            break
        
        elif auswahl == "6":
            print("Programm beendet.")
            break
        else:
            print("Ungültige Auswahl")


            