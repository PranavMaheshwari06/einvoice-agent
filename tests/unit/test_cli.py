import pytest

from einvoice.cli import build_parser, main


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
