import csv
import os
from decimal import Decimal
from datetime import datetime

#Speichert die Bestellung dauerhaft in der Datei "orders.csv"
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
