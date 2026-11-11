import csv
from pathlib import Path

from einvoice.synth.catalogue import CATEGORIES

SKR03_SUBSET = Path(__file__).parents[3] / "data/rules/skr03_subset.csv"

# The numbers are checked against the DATEV Standardkontenrahmen SKR 03 (Art.-Nr. 11174, valid
# 2026). The names are this project's own short forms: the DATEV list may not be reprinted.
CHECKED_ACCOUNTS = {
    "0420": "Büroeinrichtung",
    "0480": "Geringwertige Wirtschaftsgüter",
    "3300": "Wareneingang 7 % Vorsteuer",
    "3400": "Wareneingang 19 % Vorsteuer",
    "4210": "Miete",
    "4240": "Gas, Strom, Wasser",
    "4260": "Instandhaltung betrieblicher Räume",
    "4360": "Versicherungen",
    "4530": "Laufende Kfz-Betriebskosten",
    "4600": "Werbekosten",
    "4650": "Bewirtungskosten",
    "4660": "Reisekosten Arbeitnehmer",
    "4800": "Reparaturen und Instandhaltung",
    "4806": "Wartungskosten für Hard- und Software",
    "4910": "Porto",
    "4920": "Telefon",
    "4930": "Bürobedarf",
    "4940": "Zeitschriften und Bücher",
    "4945": "Fortbildungskosten",
    "4950": "Rechts- und Beratungskosten",
    "4955": "Buchführungskosten",
    "4964": "Lizenzen und Software-Überlassung",
    "4970": "Nebenkosten des Geldverkehrs",
    "4980": "Betriebsbedarf",
    "4985": "Werkzeuge und Kleingeräte",
}


def read_subset() -> dict[str, str]:
    with SKR03_SUBSET.open(encoding="utf-8", newline="") as file:
        return {row["account"]: row["name"] for row in csv.DictReader(file)}


def test_subset_holds_exactly_the_accounts_checked_against_the_datev_list():
    assert read_subset() == CHECKED_ACCOUNTS


def test_every_catalogue_account_is_in_the_subset():
    used = {
        account
        for items in CATEGORIES.values()
        for item in items
        for account in (item.account, item.alt_account)
        if account is not None
    }
    assert used <= set(read_subset())
