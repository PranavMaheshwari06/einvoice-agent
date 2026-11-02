import shutil

import numpy as np
import pytest

from conftest import FIXTURES, FakeDatabase, stub_encode
from einvoice.agent import rag
from einvoice.agent.rag import Chunk

POLICY = FIXTURES.parents[1] / "data" / "rules" / "ap_policy.md"
SCHEMATRON = FIXTURES / "kosit" / "XRechnung-UBL-validation.xsl"


def test_ustg_gives_one_chunk_per_absatz_of_paragraph_14():
    chunks = rag.ustg_chunks(FIXTURES / "ustg")
    assert [chunk.source_id for chunk in chunks] == ["UStG-14-1", "UStG-14-2", "UStG-14-4"]
    assert chunks[2].title == "§ 14 Abs. 4 UStG"
    assert chunks[0].body == "(1) Erster Absatz, Satz eins. Satz zwei."
    assert "1. erster Punkt; 2. zweiter Punkt." in chunks[1].body


def test_ustg_without_paragraph_14_is_refused(tmp_path):
    (tmp_path / "other.xml").write_text(
        "<dokumente><norm><metadaten><enbez>§ 1</enbez></metadaten></norm></dokumente>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no § 14"):
        rag.ustg_chunks(tmp_path)


def test_policy_gives_one_chunk_per_heading():
    chunks = rag.policy_chunks(POLICY.read_text(encoding="utf-8"))
    ids = [chunk.source_id for chunk in chunks]
    assert ids == [
        "AP-automatic-booking",
        "AP-purchase-order-matching",
        "AP-price-tolerance",
        "AP-goods-receipt",
        "AP-vendor-master-data",
        "AP-bank-details",
        "AP-duplicates",
        "AP-mandatory-content",
        "AP-vat-rates",
    ]
    tolerance = chunks[2]
    assert tolerance.title == "Price tolerance"
    assert "at most 2 percent" in tolerance.body


def test_br_de_rules_come_from_the_schematron_messages():
    chunks = {chunk.source_id: chunk for chunk in rag.br_de_chunks(SCHEMATRON)}
    assert len(chunks) == 39
    assert not any(source_id.startswith("BR-DEX") for source_id in chunks)
    assert (
        chunks["BR-DE-15"].body == 'Das Element "Buyer reference" (BT-10) muss übermittelt werden.'
    )


def raw_dir(tmp_path):
    xsl_dir = tmp_path / "validator-configuration-xrechnung/resources/xrechnung/3.0.2/xsl"
    xsl_dir.mkdir(parents=True)
    shutil.copy(SCHEMATRON, xsl_dir)
    shutil.copytree(FIXTURES / "ustg", tmp_path / "ustg")
    return tmp_path


def test_corpus_joins_the_three_sources_with_unique_ids(tmp_path):
    chunks = rag.corpus(raw_dir(tmp_path), POLICY)
    ids = [chunk.source_id for chunk in chunks]
    assert len(ids) == 3 + 9 + 39 == len(set(ids))


def test_corpus_needs_the_fetched_validator_configuration(tmp_path):
    with pytest.raises(ValueError, match="expected one XRechnung UBL schematron"):
        rag.corpus(tmp_path, POLICY)


def chunk(source_id: str, similarity: float) -> dict:
    return {"source_id": source_id, "title": source_id, "body": "", "similarity": similarity}


def test_weak_best_match_returns_no_chunks():
    assert rag.supported([chunk("BR-DE-15", 0.5), chunk("BR-DE-1", 0.4)], 0.8) == []
    assert rag.supported([], 0.8) == []


def test_strong_best_match_returns_all_k_chunks():
    found = [chunk("BR-DE-15", 0.9), chunk("BR-DE-1", 0.7)]
    assert rag.supported(found, 0.8) == found


def test_store_replaces_the_index_with_passage_vectors():
    conn = FakeDatabase()
    seen = []

    def encode(texts):
        seen.extend(texts)
        return np.array([[1.0, 0.5]] * len(texts))

    rag.store(conn, [Chunk("BR-DE-15", "BR-DE-15", "Buyer reference")], encode)

    assert conn.sent[0][0] == "DELETE FROM rule_chunks"
    assert conn.sent[1][1] == ("BR-DE-15", "BR-DE-15", "Buyer reference", "[1.0000000,0.5000000]")
    assert seen == ["BR-DE-15 Buyer reference"]
    assert conn.committed


def test_search_encodes_the_query_and_applies_the_cut_off():
    conn = FakeDatabase({"rule_chunks": [("BR-DE-15", "BR-DE-15", "Buyer reference", 0.91)]})
    found = rag.search(conn, stub_encode, "Leitweg-ID fehlt", 4)
    assert found == [
        {
            "source_id": "BR-DE-15",
            "title": "BR-DE-15",
            "body": "Buyer reference",
            "similarity": 0.91,
        }
    ]
    assert conn.sent[0][1]["k"] == 4

    conn = FakeDatabase({"rule_chunks": [("BR-DE-15", "BR-DE-15", "Buyer reference", 0.2)]})
    assert rag.search(conn, stub_encode, "Wetter in Berlin", 4) == []


def test_search_never_returns_more_than_max_chunks():
    conn = FakeDatabase()
    rag.search(conn, stub_encode, "alles", 1000)
    assert conn.sent[0][1]["k"] == rag.MAX_CHUNKS
