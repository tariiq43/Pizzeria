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
            kat_index = header.index("kategorie") if "kategorie" in header else 2
            preis_index = header.index("preis") if "preis" in header else 3

            for row in reader:
                try:
                    item = {
                        "id": int(row[id_index]),
                        "name": row[name_index],
                        "kategorie": row[kat_index],
                        "preis": Decimal(row[preis_index].replace(",", "."))
                    }
                    menu.append(item)
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