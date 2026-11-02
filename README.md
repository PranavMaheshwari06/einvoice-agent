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

### Quick start (until the dev container exists)

```bash
git clone https://github.com/PranavMaheshwari06/einvoice-agent.git
cd einvoice-agent
python3 -m venv .venv && source .venv/bin/activate
make install        # the sentence-transformers extra needs the PyTorch CPU wheels
make fetch          # public test data into data/raw/
make check          # ruff and the unit tests
claude              # then /check, then /build
```

On Windows, clone inside the WSL filesystem (`~/`), not under `/mnt/c`.

### Claude Code commands

- `/check`: read-only audit of the repo before a session.
- `/build [phase]`: build the phase named in `STATE.md`, document it, commit, push, hand off.
- `/verify`: close the first open UNVERIFIED line by running the real check.

### Keys

An API key, if you use one, goes in `.env` (git-ignored), never in a committed file.
`.env.example` lists the variable names.
