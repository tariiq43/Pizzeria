import csv
from decimal import Decimal

def lade_menu(dateiname):
    """Lädt das Menü aus einer CSV-Datei und gibt eine Liste von Dictionaries zurück."""
    menu = []
    try:
        with open(dateiname, mode="r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile, delimiter=";")
            header = next(reader)

            # Header-Namen in Kleinbuchstaben für flexible Erkennung
            header = [h.strip().lower() for h in header]

            # Erwartete Spaltennamen (tolerant gegenüber kleinen Abweichungen)
            id_index = header.index("id") if "id" in header else 0
            name_index = header.index("name") if "name" in header else 1
            preis_index = header.index("preis") if "preis" in header else 2

            for row in reader:
                try:
                    item = {
                        "id": int(row[id_index]),
                        "name": row[name_index],
                        "preis": Decimal(row[preis_index].replace(",", "."))
                    }
                    menu.append(item)
                except Exception:
                    continue

        return menu

    except FileNotFoundError:
        print("Menüdatei wurde nicht gefunden.")
        return []

    except Exception as e:
        print(f"Fehler beim Laden der Menüdatei: {e}")
        return []
