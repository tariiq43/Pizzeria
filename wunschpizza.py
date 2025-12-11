from decimal import Decimal
from wunschpizza_klasse import WunschPizza

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