import argparse
import json
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


def train(args: argparse.Namespace) -> None:
    from einvoice.ml.coding import E5_MODEL, E5Encoder
    from einvoice.ml.train import train as train_models

    settings = get_settings()
    report = train_models(
        args.dir, E5Encoder(), E5_MODEL, settings.mlflow_tracking_uri, Path("reports")
    )
    for name, scores in report["models"].items():
        print(f"{name}: validation {scores['validation']}")
    print(f"champion: {report['champion']} (registered as gl-coder@champion)")


def evaluate(args: argparse.Namespace) -> None:
    from functools import partial

    from einvoice.evaluate import evaluate as run_evaluation
    from einvoice.ml.coding import suggest_account
    from einvoice.ml.train import load_champion
    from einvoice.models import ValidationResult
    from einvoice.validation import kosit

    settings = get_settings()
    model, encoder = load_champion(settings.mlflow_tracking_uri)
    if args.fixtures:
        validate = lambda _xml: ValidationResult(accepted=True, errors=[])  # noqa: E731
        kosit_note = "not called (--fixtures); structured invoices counted as accepted"
    else:
        validate = partial(kosit.validate, validator_url=settings.validator_url)
        kosit_note = f"live validator at {settings.validator_url}"
    metrics = run_evaluation(
        args.dir,
        validate,
        kosit_note,
        partial(suggest_account, model),
        encoder,
        args.dir / "replay",
        Path("reports"),
    )
    print(json.dumps(metrics["test"], indent=1))
    print("wrote reports/metrics.json and reports/risk_coverage.png")


def convert(args: argparse.Namespace) -> None:
    from einvoice.convert import to_xrechnung
    from einvoice.models import STRUCTURED_FORMATS
    from einvoice.parsing.detect import detect_format
    from einvoice.pipeline import read_structured
    from einvoice.validation import kosit

    content = args.file.read_bytes()
    file_format = detect_format(content)
    if file_format not in STRUCTURED_FORMATS:
        raise SystemExit(f"{args.file} is a {file_format}; convert reads UBL, CII or ZUGFeRD")
    invoice, _ = read_structured(content, file_format)
    validator_url = get_settings().validator_url
    xml, result = to_xrechnung(invoice, lambda cii: kosit.validate(cii, validator_url))
    args.out.write_bytes(xml)
    print(f"wrote {args.out}; KoSIT accepted={result.accepted}")
    for error in result.errors:
        print(f"  {error.rule_id}: {error.message}")
    if not result.accepted:
        raise SystemExit(1)


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

    train_command = subcommands.add_parser(
        "train", help="train the GL-account models and register the champion in MLflow"
    )
    train_command.add_argument("--dir", type=Path, default=Path("data/synth"))
    train_command.set_defaults(handler=train)

    eval_command = subcommands.add_parser(
        "eval", help="risk-coverage evaluation; writes reports/metrics.json"
    )
    eval_command.add_argument("--dir", type=Path, default=Path("data/synth"))
    eval_command.add_argument(
        "--fixtures", action="store_true", help="skip KoSIT and count structured input as accepted"
    )
    eval_command.set_defaults(handler=evaluate)

    convert_command = subcommands.add_parser(
        "convert", help="write a structured invoice as XRechnung CII and validate it with KoSIT"
    )
    convert_command.add_argument("file", type=Path)
    convert_command.add_argument("--out", type=Path, required=True)
    convert_command.set_defaults(handler=convert)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    args.handler(args)
