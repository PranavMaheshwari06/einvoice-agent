"""Item catalogue of the synthetic generator: German item names mapped to SKR03 accounts."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Item:
    names: tuple[str, ...]
    unit: str  # UN/ECE Recommendation 20 unit code
    price_range: tuple[int, int]  # list price in EUR
    vat_rate: Decimal
    account: str
    # Some vendors book the same item to this account instead: the classifier needs the seller.
    alt_account: str | None = None
    max_quantity: int = 10


STANDARD = Decimal("19")
REDUCED = Decimal("7")

CATEGORIES: dict[str, tuple[Item, ...]] = {
    "office": (
        Item(
            ("Kopierpapier A4 500 Blatt", "Druckerpapier A4 weiß"),
            "C62",
            (3, 8),
            STANDARD,
            "4930",
            None,
            40,
        ),
        Item(
            ("Kugelschreiber 50er Pack", "Kugelschreiber Set blau"),
            "C62",
            (8, 20),
            STANDARD,
            "4930",
        ),
        Item(
            ("Ordner A4 breit", "Aktenordner Kunststoff"), "C62", (2, 5), STANDARD, "4930", None, 30
        ),
        Item(
            ("Tonerkartusche schwarz", "Toner schwarz kompatibel"),
            "C62",
            (60, 140),
            STANDARD,
            "4930",
            "4980",
            4,
        ),
        Item(
            ("Haftnotizen Block 12er", "Haftnotizen gelb 12 Stück"),
            "C62",
            (5, 12),
            STANDARD,
            "4930",
            None,
            20,
        ),
        Item(
            ("Bürostuhl ergonomisch", "Drehstuhl Büro Mesh"),
            "C62",
            (150, 450),
            STANDARD,
            "0650",
            "0670",
            3,
        ),
    ),
    "it": (
        Item(
            ("Software-Wartung monatlich", "Wartungsvertrag Software"),
            "MON",
            (80, 400),
            STANDARD,
            "4806",
            None,
            3,
        ),
        Item(
            ("Cloud-Lizenz pro Monat", "Software-Lizenz monatlich"),
            "MON",
            (15, 60),
            STANDARD,
            "4964",
            None,
            12,
        ),
        Item(
            ("Laptop Dockingstation", "USB-C Dockingstation"),
            "C62",
            (120, 250),
            STANDARD,
            "0670",
            "4985",
            4,
        ),
        Item(
            ("Monitor 27 Zoll", "Bildschirm 27 Zoll QHD"),
            "C62",
            (180, 400),
            STANDARD,
            "0670",
            "0650",
            4,
        ),
        Item(
            ("IT-Support Stunde", "Support Einsatz pro Stunde"),
            "HUR",
            (70, 110),
            STANDARD,
            "4806",
            "4800",
            12,
        ),
        Item(
            ("Telefon-Flatrate Monat", "Festnetz Flatrate"),
            "MON",
            (20, 50),
            STANDARD,
            "4920",
            None,
            3,
        ),
        Item(
            ("Internetanschluss Monat", "Business-Internet 250 Mbit"),
            "MON",
            (40, 90),
            STANDARD,
            "4920",
            None,
            3,
        ),
    ),
    "facility": (
        Item(
            ("Strom Abschlag", "Stromlieferung Abschlagszahlung"),
            "MON",
            (200, 900),
            STANDARD,
            "4240",
            None,
            2,
        ),
        Item(
            ("Wasser und Abwasser", "Wasserversorgung Abschlag"),
            "MON",
            (40, 150),
            REDUCED,
            "4240",
            None,
            2,
        ),
        Item(
            ("Büroreinigung monatlich", "Unterhaltsreinigung Büro"),
            "MON",
            (250, 700),
            STANDARD,
            "4260",
            None,
            2,
        ),
        Item(
            ("Hausmeisterservice Stunde", "Hausmeister Einsatz pro Stunde"),
            "HUR",
            (35, 55),
            STANDARD,
            "4260",
            "4800",
            20,
        ),
        Item(
            ("Büromiete Monat", "Miete Gewerberaum"), "MON", (1200, 3500), STANDARD, "4210", None, 2
        ),
    ),
    "travel": (
        Item(
            ("Bahnfahrt Fernverkehr", "Bahnticket Fernverkehr 2. Klasse"),
            "C62",
            (40, 180),
            REDUCED,
            "4660",
            None,
            4,
        ),
        Item(
            ("Hotelübernachtung", "Übernachtung Hotel inkl. Frühstück"),
            "DAY",
            (80, 160),
            REDUCED,
            "4660",
            "4650",
            5,
        ),
        Item(
            ("Kraftstoff Tankkarte", "Diesel Tankkarte"), "LTR", (2, 3), STANDARD, "4530", None, 60
        ),
        Item(
            ("Kfz-Werkstattstunde", "Werkstatt Arbeitszeit Fahrzeug"),
            "HUR",
            (80, 120),
            STANDARD,
            "4530",
            "4800",
            6,
        ),
    ),
    "marketing": (
        Item(
            ("Flyer Druck 1000 Stück", "Handzettel A5 1000 Stück"),
            "C62",
            (90, 250),
            STANDARD,
            "4610",
            None,
            4,
        ),
        Item(
            ("Online-Werbung Kampagne", "Anzeigenkampagne Suchmaschine"),
            "C62",
            (300, 1500),
            STANDARD,
            "4610",
            None,
            2,
        ),
        Item(
            ("Bewirtung Geschäftsessen", "Geschäftsessen Restaurant"),
            "C62",
            (60, 300),
            STANDARD,
            "4650",
            None,
            2,
        ),
        Item(
            ("Kundengeschenk Präsentkorb", "Präsentkorb Kunden"),
            "C62",
            (25, 80),
            STANDARD,
            "4610",
            "4650",
            10,
        ),
    ),
    "services": (
        Item(
            ("Steuerberatung Stunde", "Beratung Steuerrecht pro Stunde"),
            "HUR",
            (120, 220),
            STANDARD,
            "4950",
            "4955",
            10,
        ),
        Item(
            ("Buchführung monatlich", "Laufende Buchführung Monat"),
            "MON",
            (150, 500),
            STANDARD,
            "4955",
            None,
            3,
        ),
        Item(
            ("Rechtsberatung Stunde", "Anwaltliche Beratung pro Stunde"),
            "HUR",
            (180, 300),
            STANDARD,
            "4950",
            None,
            8,
        ),
        Item(
            ("Seminar Weiterbildung", "Fortbildung Seminargebühr"),
            "C62",
            (300, 1200),
            STANDARD,
            "4945",
            None,
            3,
        ),
        Item(
            ("Fachzeitschrift Jahresabo", "Zeitschrift Abonnement"),
            "C62",
            (40, 150),
            REDUCED,
            "4940",
            None,
            3,
        ),
        Item(("Fachbuch", "Fachbuch Steuern und Recht"), "C62", (20, 80), REDUCED, "4940", None, 5),
        Item(("Paketversand", "Versandkosten Paket"), "C62", (5, 20), STANDARD, "4910", None, 30),
    ),
    "goods": (
        Item(
            ("Verpackungskarton 40x30", "Versandkarton Wellpappe"),
            "C62",
            (1, 3),
            STANDARD,
            "3400",
            "4980",
            200,
        ),
        Item(
            ("Kaffee Bohnen 1 kg", "Kaffeebohnen Röstung 1 kg"),
            "KGM",
            (8, 18),
            REDUCED,
            "3300",
            "4980",
            20,
        ),
        Item(
            ("Werkzeugset 120-teilig", "Werkzeugkoffer Set"),
            "C62",
            (40, 200),
            STANDARD,
            "4985",
            "0670",
            5,
        ),
        Item(
            ("Schutzhandschuhe 12 Paar", "Arbeitshandschuhe 12 Paar"),
            "C62",
            (10, 30),
            STANDARD,
            "4980",
            "3400",
            20,
        ),
        Item(
            ("Holzbretter Eiche", "Eichenbretter gehobelt"),
            "MTR",
            (6, 25),
            STANDARD,
            "3400",
            None,
            60,
        ),
    ),
}
