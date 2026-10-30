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
