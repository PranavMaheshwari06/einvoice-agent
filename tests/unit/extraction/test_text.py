from pathlib import Path

from einvoice.extraction.text import page_texts

FIXTURES = Path(__file__).parents[2] / "fixtures"


def test_page_texts_returns_one_string_per_page():
    pages = page_texts((FIXTURES / "corpus" / "zugferd_2p0_EN16931_Einfach.pdf").read_bytes())

    assert len(pages) == 2
    assert "Handelsrechnung Nr. 471102" in pages[0]
    assert "Bruttosumme 529,87" in pages[1]
