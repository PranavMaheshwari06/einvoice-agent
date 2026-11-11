# einvoice-agent

Checks incoming German e-invoices (XRechnung, ZUGFeRD, plain PDF, scans), books
automatically only what the checks can prove, and sends the rest to a person with the
reason. Design: [docs/SPEC.md](docs/SPEC.md). Progress: [STATE.md](STATE.md). Learning
guide: [docs/GUIDE.md](docs/GUIDE.md).

This README is a placeholder. It is replaced with the project README in phase A9.

## How this repo is built

The repo is built with Claude Code, one session per step. `STATE.md` lists the sessions, the
branch each one uses, and a "Next session" block with the first message to paste. Work can
continue in a cloud session or in VS Code on the laptop; both read the same files.

Each phase has two parts. `build` is code plus unit tests, which needs no services. `live`
runs the phase against the real Postgres, KoSIT validator, LLM and Docker. A phase counts as
finished only when both are done.

### Quick start

Needs Docker with Compose. Python, tesseract (with the German data) and the pinned packages
live in the dev container; Postgres with pgvector and the KoSIT validator run beside it.

```bash
git clone https://github.com/PranavMaheshwari06/einvoice-agent.git
cd einvoice-agent
make up             # builds the images, starts dev, postgres and validator
```

Then open the folder in VS Code and choose "Reopen in Container". In the container terminal:

```bash
make fetch              # public test data into data/raw/
make check              # ruff and the unit tests
make test-integration   # tests that call Postgres and the validator
claude                  # then /check, then /build
```

Without VS Code, run a command in the container with
`docker compose -f deploy/compose.yaml exec dev make check`. `make down` stops the services; the
database and the Hugging Face model cache stay in Docker volumes.

`requirements.lock` pins every package, with the PyTorch CPU wheels. After changing
`pyproject.toml`, run `make lock` on the host and rebuild with `make up`.

On Windows, clone inside the WSL filesystem (`~/`), not under `/mnt/c`.

### Claude Code commands

- `/check`: read-only audit of the repo before a session.
- `/build [phase]`: build the phase named in `STATE.md`, document it, commit, push, hand off.
- `/verify`: close the first open UNVERIFIED line by running the real check.

### Keys

An API key, if you use one, goes in `.env` (git-ignored), never in a committed file.
`.env.example` lists the variable names.

## Limitations

- The ZUGFeRD PDFs that `einvoice seed` writes are not valid PDF/A-3. I ran two of them through
  Mustang 2.26.0, which includes veraPDF, and both fail the same two rules: the Helvetica fonts
  are not embedded, and DeviceGray is used without an output intent. The XML inside the one
  without an injected error passed Mustang's XML check, and my parsers and rules read these
  files. A strict PDF/A check would still reject them.
- The mandatory-field rule gives every invoice with a gross total up to 250 EUR the small-invoice
  relief of §33 UStDV, but §33 excludes invoices for services under §§ 3c, 6a and 13b UStG, which
  the rule does not check, so it can accept such an invoice with fields missing that §14 UStG requires.
