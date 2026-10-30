"""Download the public data sources into data/raw/ and write DATA_SOURCES.md."""

import argparse
import io
import shutil
import tarfile
import zipfile
from datetime import date
from functools import partial
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GITHUB_API = "https://api.github.com/repos"
USTG_URL = "https://www.gesetze-im-internet.de/ustg_1980/xml.zip"


def get(client: httpx.Client, url: str) -> httpx.Response:
    response = client.get(url)
    response.raise_for_status()
    return response


def latest_release_asset(client: httpx.Client, repo: str, suffix: str) -> tuple[str, str]:
    """Return (tag, download url) of the release asset whose name ends with suffix."""
    release = get(client, f"{GITHUB_API}/{repo}/releases/latest").json()
    for asset in release["assets"]:
        if asset["name"].endswith(suffix):
            return release["tag_name"], asset["browser_download_url"]
    raise RuntimeError(f"{repo}: no release asset ending in {suffix!r}")


def unzip(content: bytes, target: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        archive.extractall(target)


def fetch_release_zip(client: httpx.Client, target: Path, repo: str) -> tuple[str, str]:
    tag, url = latest_release_asset(client, repo, ".zip")
    unzip(get(client, url).content, target)
    return tag, url


def fetch_zugferd_corpus(client: httpx.Client, target: Path) -> tuple[str, str]:
    commit = get(client, f"{GITHUB_API}/ZUGFeRD/corpus/commits/master").json()["sha"]
    url = f"https://codeload.github.com/ZUGFeRD/corpus/tar.gz/{commit}"
    with tarfile.open(fileobj=io.BytesIO(get(client, url).content), mode="r:gz") as archive:
        archive.extractall(target, filter="data")
    return commit[:12], url


def fetch_validator_jar(client: httpx.Client, target: Path) -> tuple[str, str]:
    tag, url = latest_release_asset(client, "itplr-kosit/validator", "-standalone.jar")
    target.mkdir(parents=True, exist_ok=True)
    (target / url.rsplit("/", 1)[-1]).write_bytes(get(client, url).content)
    return tag, url


def fetch_ustg(client: httpx.Client, target: Path) -> tuple[str, str]:
    unzip(get(client, USTG_URL).content, target)
    return date.today().isoformat(), USTG_URL


def write_data_sources(rows: list[tuple[str, str, str, str]]) -> None:
    lines = [
        "# Data sources",
        "",
        "Written by `scripts/fetch_data.py`. Raw files are in `data/raw/` and are not committed.",
        "",
        "| Source | Version | URL | Licence |",
        "|---|---|---|---|",
    ]
    lines += [f"| {name} | {version} | {url} | {licence} |" for name, version, url, licence in rows]
    lines += [
        "",
        "Written for this project: `data/rules/ap_policy.md` and `data/rules/skr03_subset.csv`",
        "(project licence). Synthetic invoices come from `einvoice.synth` and are generated.",
        "No real personal or company data is used.",
        "",
    ]
    (ROOT / "DATA_SOURCES.md").write_text("\n".join(lines), encoding="utf-8")


JOBS = [
    ("ZUGFeRD corpus", "zugferd-corpus", "Apache-2.0", fetch_zugferd_corpus),
    (
        "XRechnung testsuite",
        "xrechnung-testsuite",
        "Apache-2.0",
        partial(fetch_release_zip, repo="itplr-kosit/xrechnung-testsuite"),
    ),
    ("KoSIT validator (jar)", "validator", "Apache-2.0", fetch_validator_jar),
    (
        "KoSIT validator configuration XRechnung",
        "validator-configuration-xrechnung",
        "Apache-2.0",
        partial(fetch_release_zip, repo="itplr-kosit/validator-configuration-xrechnung"),
    ),
    ("UStG (gesetze-im-internet.de)", "ustg", "official work, §5 UrhG", fetch_ustg),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="download again if a folder exists")
    force = parser.parse_args().force

    rows = []
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for name, folder, licence, fetch in JOBS:
            target = RAW / folder
            if target.exists() and force:
                shutil.rmtree(target)
            if target.exists():
                print(f"skip {name}: {target} exists (use --force)")
                continue
            target.mkdir(parents=True)
            version, url = fetch(client, target)
            rows.append((name, version, url, licence))
            print(f"fetched {name} {version}")

    # A partial run cannot rebuild the table, so it keeps the existing DATA_SOURCES.md.
    if len(rows) == len(JOBS):
        write_data_sources(rows)


if __name__ == "__main__":
    main()
