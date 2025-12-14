Pizzeria Sunshine - Bestellsystem 
Ein einfaches Bestellsystem für eine Pizzeria, gemacht von Studierenden mit Python.  
 
Beschreibung 
 
Mit diesem Programm können Kunden Pizzas und Getränke bestellen.
Das System verwaltet das Menü, den Warenkorb und erstellt automatisch Quittungen. 
Kunden können auch ihre eigene Pizza mit individuellen Zutaten zusammenstellen. 
Alle Bestellungen werden gespeichert und können später wieder angesehen werden. 
 
 
Funktionen 
 
Menü anzeigen – Alle verfügbaren Pizzas und Getränke mit Preisen ansehen 
Artikel in den Warenkorb legen – Produkte auswählen und hinzufügen 
Eigene Pizza zusammenstellen – Wunschpizza mit selbst gewählten Zutaten kreieren 
Warenkorb verwalten – Artikel ansehen, Menge ändern oder löschen 
Bestellung abschliessen – Bestellung fertigstellen und bezahlen 
Quittung automatisch generieren – Rechnung wird ausgedruckt und gespeichert 
Bestellverlauf speichern – Alle Bestellungen werden gespeichert 
Bestellverlauf abrufen – Frühere Bestellungen können angesehen werden 
 
 
Voraussetzungen  
Python 3.x 
Keine zusätzlichen Module erforderlich 
 
 
Installation  
https://github.com/tariiq43/Pizzeria.git 
 
 
Verwendung  
 
Programm starten: Python main.py  
 
 
Nach dem Start sieht man ein Menü mit 6 Optionen: 
1: Menü anzeigen 
2: Bestellung aufgeben  
3: Warenkorb anzeigen 
4: Bestellung abschliessen 
5: Bestellung anzeigen 
6: Beenden 
 
 
 
Projektstruktur  
 
 
Pizzeria/ 
├── main.py                		 Hauptprogramm – startet das System 
├── artikel_einlesen.py    	   Liest Menü aus CSV-Datei 
├── shop.py               		 Zeigt Menü und verwaltet den Warenkorb 
├── wunschpizza_klasse.py  	   Klasse für Wunschpizza-Objekte 
├── wunschpizza.py        	   Zusammenstellen von Wunschpizzen 
├── bestellung.py           	 Speichert Bestellungen und erstellt Quittungen 
├── Menü_Pizzeria.csv      	   Alle Artikel (Pizzas, Getränke) mit Preisen 
├── bestellungen.csv        	 Alle gespeicherten Bestellungen 
├── quittung_<order_id>.txt  	 Quittung der Bestellung 
└── README.md              	   Diese Datei 
 
 
Wie das System funktioniert 

Programm-Start (main.py) 
Das Programm startet  
Zeigt das Hauptmenü 

Menü laden (artikel_einlesen.py) 
Liest alle verfügbaren Artikel aus Menü Pizzeria.csv 
Macht Pizzas und Getränke verfügbar 

Shop-Funktionen (shop.py) 
Berechnet Zwischen-und Gesamtpreis 
Zeigt Menü und Warenkorb an 
Nimmt Eingaben entgegen 

Wunschpizza-Klasse (wunschpizza_klasse.py) 
Definiert die Wunschpizza als Klasse 
Speichert Zutaten und Preis 
Prüft, ob die Pizza gültig ist (mindestens eine Zutat)  

Wunschpizza-Funktion (wunschpizza.py) 
Kunden können ihre eigene Pizza zusammenstellen 
System berechnet Preis automatisch 
Wunschpizza wird wie normale Pizza behandelt 

Bestellungen verwalten (bestellung.py) 
Erstellt neue Bestellungen 
Speichert Bestellungen am Ende 

Quittung & Speicherung 
Nach Bestellung wird Quittung generiert 
Alle Daten werden in bestellungen.csv gespeichert 
 
 
 
 
 
 
Dateiformat  
 
Menü Pizzeria.csv 

Enthält alle Artikel mit Namen und Preisen 
Format: Artikel-ID, Name, Preis, Kategorie 
Wird beim Start automatisch geladen 

orders.csv 

Speichert alle abgeschlossenen Bestellungen 
Enthält: Datum, Artikel, Menge, Gesamtpreis 
Kann später zur Ansicht geladen werden 
 
Besonderheiten 
 
Benutzerfreundlich – Einfaches Menü mit nur 6 Optionen 
Wunschpizza – Kunden können ihre eigene Pizza kreieren 
Automatische Quittung – Keine manuelle Eingabe nötig 
Übersichtlich – Klare Struktur und einfache Navigation 
 
 
Autoren 
Mohammed Alhassan 
Younus Tariq 
Irem Camkiran 
 
Lizenz 
Dieses Projekt wurde für Lernzwecke erstellt.  
