from decimal import Decimal
from wunschpizza_klasse import WunschPizza

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
   
    #Entfernt eine Zutat, falls sie vorhanden
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
