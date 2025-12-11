# Benötigte Module importieren (csv, dezimalzahlen, datum/zeit)
import csv
from decimal import Decimal
import os
from datetime import datetime
from artikel_einlesen import lade_menu
from wunschpizza_klasse import WunschPizza
from wunschpizza import wunschpizza_erstellen
from bestellung import bestellung_in_csv_speichern

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
                f"CHF {artikel['preis']:>6.2f} = CHF {artikel_gesamtpreis:>10.2f}\n"
            )

        f.write("-" * 60 + "\n")
        f.write(f"{'GESAMTPREIS':<35} CHF {gesamtpreis:>10.2f}\n")
        f.write("=" * 60 + "\n")
        f.write("Vielen Dank für Ihre Bestellung!\n")

# Gibt das Menü formatiert im Terminal aus
def zeige_menu(menu):
    """Zeigt das Menü formatiert an."""
    print("\n--- Menü Pizzeria Sunshine ---")
    for item in menu:
        print(f"{item['id']:>2}. {item['name']:<25} {item['preis']:.2f} CHF")         
    print("--------------------------------")

# Sucht in der Menü-Liste nach einer Artikel-ID und gibt den Artikel
def finde_artikel(menu, artikel_id):
    """Sucht einen Artikel anhand seiner ID."""
    for item in menu:
        if item["id"] == artikel_id:
            return item
    return None

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
        print(f"{item['menge']}x {item['name']:<25} = {zwischensumme:>10.2f} CHF")

    print(f"{'':>2} {'Gesamtpreis':<25} = {gesamt:10.2f} CHF")


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
        if artikel_id == 21:
            wunschpizza_erstellen(menu, warenkorb)
            return
        
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



if __name__ == "__main__":
    menu = lade_menu("Menü Pizzeria.csv") # Menü wird aus der CSV-Datei geladen
    warenkorb = {}

    if not menu:
        exit()

# Hauptmenü anzeigen
    while True:
        print("\n1. Menü anzeigen")
        print("2. Bestellung aufgeben")
        print("3. Warenkorb anzeigen")
        print("4. Bestellung abschliessen")
        print("5. Bestellung anzeigen")
        print("6. Beenden")


        auswahl = input("Bitte wählen:")

        if auswahl == "1":
            zeige_menu(menu)

        elif auswahl == "2":
            artikel_hinzufuegen(menu, warenkorb)

        elif auswahl == "3":
            zeige_warenkorb(warenkorb)

        elif auswahl == "4":
            jetzt = datetime.now()
            order_id = int(jetzt.timestamp()) # Bestellnummer setzen (Zeitstempel)
            gesamtpreis = sum(artikel["preis"] * artikel["menge"]for artikel in warenkorb.values())

            # Bestellung wir dauerhaft gespeichert
            bestellung_in_csv_speichern(warenkorb, order_id, jetzt, gesamtpreis)
            # Quittung wird als TXT erzeugt
            quittung_als_textdatei_speichern(warenkorb, order_id, jetzt,gesamtpreis)

            print("\nBestellung gespeichert und Quittung erstellt.\n")
            
        
        elif auswahl == "5":
            zeige_warenkorb(warenkorb)

        elif auswahl == "6": 
            print("Programm beendet")
            break
    
        else:
            print("Ungültige Auswahl")

