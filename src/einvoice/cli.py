import argparse
import logging
import re
from collections.abc import Sequence
from pathlib import Path

from einvoice.config import get_settings


def show_config(_args: argparse.Namespace) -> None:
    settings = get_settings()
    for name, value in settings.model_dump().items():
        # The database URL carries the password; never print it.
        shown = re.sub(r"://[^@/]*@", "://***@", value) if name == "database_url" else value
        print(f"{name.upper()}={shown}")


def seed(args: argparse.Namespace) -> None:
    from einvoice.synth.generate import generate

    logging.getLogger("drafthorse").setLevel(logging.WARNING)
    args.out.mkdir(parents=True, exist_ok=True)
    generate(args.seed, args.out, args.count)
    print(f"wrote {args.count} invoices and their master data and gold labels to {args.out}")


def db_migrate(_args: argparse.Namespace) -> None:
    from einvoice.db import db

    with db.connect(get_settings().database_url) as conn:
        applied = db.migrate(conn)
    print(f"applied {len(applied)} migration(s)" + (f": {', '.join(applied)}" if applied else ""))


def db_load(args: argparse.Namespace) -> None:
    from einvoice.db import db

    with db.connect(get_settings().database_url) as conn:
        db.load_master_data(conn, args.dir)
    print(f"loaded master data from {args.dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="einvoice", description="German e-invoice AP pipeline")
    subcommands = parser.add_subparsers(dest="command", required=True)
    config = subcommands.add_parser("config", help="print the settings the program would use")
    config.set_defaults(handler=show_config)

    seed_command = subcommands.add_parser(
        "seed", help="generate synthetic invoices and gold labels"
    )
    seed_command.add_argument("--seed", type=int, default=1)
    seed_command.add_argument("--out", type=Path, default=Path("data/synth"))
    seed_command.add_argument("--count", type=int, default=2000)
    seed_command.set_defaults(handler=seed)

    database = subcommands.add_parser("db", help="database commands")
    database_commands = database.add_subparsers(dest="db_command", required=True)
    migrate = database_commands.add_parser("migrate", help="apply the SQL migrations")
    migrate.set_defaults(handler=db_migrate)
    load = database_commands.add_parser("load", help="load vendors and purchase orders from seed")
    load.add_argument("--dir", type=Path, default=Path("data/synth"))
    load.set_defaults(handler=db_load)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    args.handler(args)
