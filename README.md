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

In VS Code, open Copilot Chat, switch to **Agent** mode, and type `/build`.
If prompt files are switched off, open `.github/prompts/build.prompt.md` and paste
its text (everything below the `---` block) into the chat.

Approve the terminal commands Copilot asks to run (pip, pytest, ruff, git commit).
If a chat gets long or ends, open a new one and type `/build` again; it continues from
`STATE.md`. When Copilot says "Stage A done", run `git push`.

### Stage B (your own machine, Claude Code)

```bash
git clone https://github.com/PranavMaheshwari06/einvoice-agent.git
cd einvoice-agent
claude
```

Then: "Continue from STATE.md, Stage B, starting with B0." Install Docker Desktop, kind,
kubectl and Ollama first if they are missing. An API key, if you use one, goes in `.env`
(git-ignored), never in a committed file.
