from datetime import datetime
from artikel_einlesen import lade_menu
from bestellung import bestellung_in_csv_speichern
from shop import (zeige_menu, artikel_hinzufuegen, zeige_warenkorb, quittung_als_textdatei_speichern)


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

