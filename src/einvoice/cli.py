import argparse
import logging
import re
from collections.abc import Sequence

from einvoice.config import get_settings


def show_config(_args: argparse.Namespace) -> None:
    settings = get_settings()
    for name, value in settings.model_dump().items():
        # The database URL carries the password; never print it.
        shown = re.sub(r"://[^@/]*@", "://***@", value) if name == "database_url" else value
        print(f"{name.upper()}={shown}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="einvoice", description="German e-invoice AP pipeline")
    subcommands = parser.add_subparsers(dest="command", required=True)
    config = subcommands.add_parser("config", help="print the settings the program would use")
    config.set_defaults(handler=show_config)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    args.handler(args)
