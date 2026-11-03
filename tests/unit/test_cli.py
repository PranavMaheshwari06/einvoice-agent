import json

import pytest

from conftest import FIXTURES
from einvoice.cli import build_parser, main
from einvoice.models import RuleViolation, ValidationResult
from einvoice.parsing.detect import detect_format


def test_help_lists_subcommands(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "config" in capsys.readouterr().out


def test_subcommand_is_required():
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args([])
    assert exit_info.value.code == 2


def test_config_hides_database_password(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@db:5432/x")
    main(["config"])
    out = capsys.readouterr().out
    assert "secret" not in out
    assert "DATABASE_URL=postgresql://***@db:5432/x" in out


def test_seed_writes_invoices_master_data_and_gold(tmp_path, capsys):
    main(["seed", "--seed", "1", "--out", str(tmp_path), "--count", "6"])
    assert len(list((tmp_path / "invoices").iterdir())) == 6
    assert len((tmp_path / "gold.jsonl").read_text().splitlines()) == 6
    assert (tmp_path / "vendors.json").exists()
    assert (tmp_path / "purchase_orders.json").exists()
    assert "wrote 6 invoices" in capsys.readouterr().out


def test_db_commands_are_listed(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["db", "--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert "migrate" in out
    assert "load" in out


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def test_db_migrate_reports_applied_files(monkeypatch, capsys):
    from einvoice.db import db

    monkeypatch.setattr(db, "connect", lambda _url: FakeConnection())
    monkeypatch.setattr(db, "migrate", lambda _conn: ["001_init.sql"])

    main(["db", "migrate"])

    assert "applied 1 migration(s): 001_init.sql" in capsys.readouterr().out


def test_db_migrate_says_when_nothing_was_applied(monkeypatch, capsys):
    from einvoice.db import db

    monkeypatch.setattr(db, "connect", lambda _url: FakeConnection())
    monkeypatch.setattr(db, "migrate", lambda _conn: [])

    main(["db", "migrate"])

    assert capsys.readouterr().out.strip() == "applied 0 migration(s)"


def test_db_load_passes_the_directory_to_the_loader(monkeypatch, tmp_path, capsys):
    from einvoice.db import db

    loaded = []
    monkeypatch.setattr(db, "connect", lambda _url: FakeConnection())
    monkeypatch.setattr(db, "load_master_data", lambda _conn, directory: loaded.append(directory))

    main(["db", "load", "--dir", str(tmp_path)])

    assert loaded == [tmp_path]
    assert f"loaded master data from {tmp_path}" in capsys.readouterr().out


def test_model_and_eval_commands_are_listed(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert all(name in out for name in ("train", "eval", "convert"))


UBL = FIXTURES / "xrechnung" / "01.01a-INVOICE_ubl.xml"


def _kosit(monkeypatch, accepted: bool) -> None:
    from einvoice.validation import kosit

    errors = [] if accepted else [RuleViolation(rule_id="BR-DE-1", level="error", message="x")]
    result = ValidationResult(accepted=accepted, errors=errors)
    monkeypatch.setattr(kosit, "validate", lambda xml, validator_url: result)


def test_convert_writes_cii_and_reports_kosit(monkeypatch, tmp_path, capsys):
    _kosit(monkeypatch, accepted=True)
    out = tmp_path / "out.xml"
    main(["convert", str(UBL), "--out", str(out)])
    assert detect_format(out.read_bytes()) == "cii"
    assert "KoSIT accepted=True" in capsys.readouterr().out


def test_convert_fails_when_kosit_rejects(monkeypatch, tmp_path, capsys):
    _kosit(monkeypatch, accepted=False)
    with pytest.raises(SystemExit) as exit_info:
        main(["convert", str(UBL), "--out", str(tmp_path / "out.xml")])
    assert exit_info.value.code == 1
    assert "BR-DE-1" in capsys.readouterr().out


def test_convert_refuses_a_plain_pdf(tmp_path):
    with pytest.raises(SystemExit, match="convert reads UBL, CII or ZUGFeRD"):
        main(["convert", str(FIXTURES / "synth" / "inv_00001.pdf"), "--out", str(tmp_path / "x")])


def test_eval_with_fixtures_says_kosit_was_not_called(monkeypatch, gold_dir, gl_model, tmp_path):
    from einvoice.ml import train

    monkeypatch.setattr(train, "load_champion", lambda _uri: (gl_model, "tfidf"))
    monkeypatch.chdir(tmp_path)
    main(["eval", "--dir", str(gold_dir), "--fixtures"])
    metrics = json.loads((tmp_path / "reports" / "metrics.json").read_text())
    assert metrics["kosit"].startswith("not called (--fixtures)")
    assert metrics["encoder"] == "tfidf"


def test_eval_record_needs_a_real_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "replay")
    with pytest.raises(SystemExit, match="--record needs a real LLM_PROVIDER"):
        main(["eval", "--dir", str(tmp_path), "--record"])


def test_db_index_embeds_the_corpus_with_the_passage_prefix(monkeypatch, capsys):
    from einvoice.agent import rag
    from einvoice.agent.rag import Chunk
    from einvoice.db import db

    stored = []
    monkeypatch.setattr(db, "connect", lambda _url: FakeConnection())
    monkeypatch.setattr(rag, "corpus", lambda _raw, _policy: [Chunk("BR-DE-15", "BR-DE-15", "")])
    monkeypatch.setattr(rag, "store", lambda _conn, chunks, encoder: stored.append(encoder))

    main(["db", "index"])

    assert stored[0]._prefix == "passage: "
    assert "indexed 1 rule chunks" in capsys.readouterr().out


def test_agent_eval_writes_the_report(monkeypatch, tmp_path, capsys):
    from einvoice import cli
    from einvoice.agent import evals, rag
    from einvoice.agent.rag import Chunk

    cases = FIXTURES.parents[1] / cli.AGENT_CASES
    ids = {source_id for case in evals.load_cases(cases) for source_id in case["rules"]}
    chunks = [Chunk(source_id, source_id, "") for source_id in ids]
    monkeypatch.setattr(cli, "AGENT_CASES", cases)
    monkeypatch.setattr(cli, "REPLAY_DIR", FIXTURES / "replay")
    monkeypatch.setattr(rag, "corpus", lambda _raw, _policy: chunks)
    monkeypatch.setenv("LLM_PROVIDER", "replay")
    monkeypatch.chdir(tmp_path)

    main(["agent-eval"])

    report = json.loads((tmp_path / "reports" / "agent_eval.json").read_text())
    assert report["model"] == "replay"
    assert f"{report['passed']} of {report['cases']} cases passed" in capsys.readouterr().out
