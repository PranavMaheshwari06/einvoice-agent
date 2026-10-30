# einvoice-agent

Checks incoming German e-invoices (XRechnung, ZUGFeRD, plain PDF, scans), books
automatically only what the checks can prove, and sends the rest to a person with the
reason. Design: [docs/SPEC.md](docs/SPEC.md). Progress: [STATE.md](STATE.md).

This README is a placeholder. It is replaced with the project README in phase A9.

## How this repo is built

Stage A writes the code and runs the unit tests (no services, no keys). Stage B runs
everything: database, validator, LLM, Docker, Kubernetes, CI, Azure.

### Stage A (WSL, VS Code, GitHub Copilot)

```bash
cd ~
git clone https://github.com/PranavMaheshwari06/einvoice-agent.git
cd einvoice-agent
git config user.name "<your name>"
git config user.email "<your personal email>"   # this repo only; keeps a work email out of the history
python3 -m venv .venv
code .
```

The build runs in 8 chunks (table in `STATE.md`), one chat each. For every chunk:

1. New Copilot Chat, **Agent** mode, pick the model `STATE.md` names for the next chunk
   (Sonnet or Opus, newest of that tier).
2. Type `/check`. It must end with `Verdict: READY` (skip it before chunk 1).
3. Type `/build`. Approve the terminal commands (pip, pytest, ruff, git commit). It builds
   that chunk, commits per phase, prints a summary and stops.
4. Read the summary: `ruff` pass, pytest passed, new UNVERIFIED lines. Then `git push`
   (the repo is the backup) and go back to step 1.

If prompt files are switched off, open `.github/prompts/build.prompt.md` or
`check.prompt.md` and paste the text below the `---` block into the chat.
When Copilot says "Stage A done", run `git push` and move to Stage B.

If you change a file on the personal machine (like this one), run `git pull` in the WSL
terminal before the next chunk. Reloading the VS Code window does not fetch anything.

### Stage B (your own machine, Claude Code)

```bash
git clone https://github.com/PranavMaheshwari06/einvoice-agent.git
cd einvoice-agent
claude
```

Then: "Continue from STATE.md, Stage B, starting with B0." Install Docker Desktop, kind,
kubectl and Ollama first if they are missing. An API key, if you use one, goes in `.env`
(git-ignored), never in a committed file.
