"""Rule texts the agent may cite: §14 UStG, the AP policy and the BR-DE rules, in pgvector."""

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import psycopg
from lxml import etree

from einvoice.ml.coding import Encoder
from einvoice.parsing.xmltools import parse_xml

# e5 retrieval prefixes (microsoft/unilm, e5/mteb_beir_eval.py): queries and indexed texts differ.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
SVRL_NS = {"svrl": "http://purl.oclc.org/dsdl/svrl"}
# Provisional: e5 cosine scores of unrelated texts sit high, so the cut-off must be set from
# live queries (STATE.md UNVERIFIED, A5 live).
MIN_SIMILARITY = 0.80
# Every returned chunk becomes citable, so the model must not fetch the whole corpus at once.
MAX_CHUNKS = 8


@dataclass(frozen=True)
class Chunk:
    source_id: str
    title: str
    body: str


def _squash(text: str) -> str:
    return " ".join(text.split())


def ustg_chunks(directory: Path) -> list[Chunk]:
    """One chunk per Absatz of §14 from the gesetze-im-internet.de XML in `directory`."""
    for path in sorted(directory.glob("*.xml")):
        for norm in parse_xml(path.read_bytes()).iter("norm"):
            if norm.findtext("metadaten/enbez") == "§ 14":
                paragraphs = norm.iterfind("textdaten/text/Content/P")
                return [_absatz(paragraph) for paragraph in paragraphs]
    raise ValueError(f"no § 14 in the UStG XML under {directory}")


def _absatz(paragraph: etree._Element) -> Chunk:
    body = _squash(" ".join(paragraph.itertext()))
    number = re.match(r"\((\d+[a-z]?)\)", body)
    if number is None:
        raise ValueError(f"§ 14 paragraph does not start with an Absatz number: {body[:40]!r}")
    absatz = number.group(1)
    return Chunk(f"UStG-14-{absatz}", f"§ 14 Abs. {absatz} UStG", body)


def policy_chunks(markdown: str) -> list[Chunk]:
    """One chunk per `##` heading of the AP policy; the introduction is not a rule."""
    chunks = []
    for section in markdown.split("\n## ")[1:]:
        heading, _, body = section.partition("\n")
        slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
        chunks.append(Chunk(f"AP-{slug}", heading.strip(), _squash(body)))
    return chunks


def br_de_chunks(xsl: Path) -> list[Chunk]:
    """One chunk per BR-DE rule, with the message text of the XRechnung schematron."""
    asserts = parse_xml(xsl.read_bytes()).xpath(
        "//svrl:failed-assert[starts-with(@id, 'BR-DE-')]", namespaces=SVRL_NS
    )
    chunks = {}
    for element in asserts:
        rule_id = element.get("id")
        text = _squash(" ".join(element.find("svrl:text", SVRL_NS).itertext()))
        chunks[rule_id] = Chunk(rule_id, rule_id, text.removeprefix(f"[{rule_id}] "))
    return list(chunks.values())


def corpus(raw: Path, policy: Path) -> list[Chunk]:
    """All chunks from the fetched sources (`scripts/fetch_data.py`) and the AP policy."""
    xsl_files = sorted(
        raw.glob(
            "validator-configuration-xrechnung/resources/xrechnung/*/xsl/"
            "XRechnung-UBL-validation.xsl"
        )
    )
    if len(xsl_files) != 1:
        raise ValueError(f"expected one XRechnung UBL schematron under {raw}, found {xsl_files}")
    chunks = (
        ustg_chunks(raw / "ustg")
        + policy_chunks(policy.read_text(encoding="utf-8"))
        + br_de_chunks(xsl_files[0])
    )
    ids = [chunk.source_id for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("rule chunks have duplicate source ids")
    return chunks


def _vector(values: np.ndarray) -> str:
    """pgvector's text input format, so no type adapter has to be registered on the connection."""
    return "[" + ",".join(f"{value:.7f}" for value in values) + "]"


def store(conn: psycopg.Connection, chunks: list[Chunk], encode: Encoder) -> None:
    """Replace the indexed chunks; `encode` must use `PASSAGE_PREFIX`."""
    vectors = encode([f"{chunk.title} {chunk.body}" for chunk in chunks])
    rows = [
        (chunk.source_id, chunk.title, chunk.body, _vector(vector))
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM rule_chunks")
        cursor.executemany(
            "INSERT INTO rule_chunks (source_id, title, body, embedding) "
            "VALUES (%s, %s, %s, %s::vector)",
            rows,
        )
    conn.commit()


def nearest(conn: psycopg.Connection, query_vector: np.ndarray, k: int) -> list[dict]:
    rows = conn.execute(
        "SELECT source_id, title, body, 1 - (embedding <=> %(query)s::vector) AS similarity "
        "FROM rule_chunks ORDER BY embedding <=> %(query)s::vector LIMIT %(k)s",
        {"query": _vector(query_vector), "k": k},
    ).fetchall()
    return [
        {"source_id": source_id, "title": title, "body": body, "similarity": round(score, 3)}
        for source_id, title, body, score in rows
    ]


def supported(chunks: list[dict], min_similarity: float) -> list[dict]:
    """No chunks at all when even the best one is below `min_similarity` (SPEC 3.7)."""
    if not chunks or chunks[0]["similarity"] < min_similarity:
        return []
    return chunks


def search(conn: psycopg.Connection, encode: Encoder, query: str, k: int) -> list[dict]:
    """The `k` nearest chunks (at most `MAX_CHUNKS`); `encode` must use `QUERY_PREFIX`."""
    return supported(nearest(conn, encode([query])[0], min(k, MAX_CHUNKS)), MIN_SIMILARITY)
