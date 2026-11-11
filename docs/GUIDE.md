# Guide to the project

For the owner, to learn and explain the project. Extended in every phase. Design decisions are
in `docs/SPEC.md`, per-component notes in `docs/notes/`, history in `docs/PHASE_LOG.md`.

## What the project does

An accounts-payable team receives invoices as XML, PDFs with embedded XML, plain PDFs and
scans. The pipeline reads each one into the same `Invoice` model, checks it against the rules
a booking clerk would apply, and either proposes a booking automatically or sends it to a
person with the reasons. Models read and explain; rules decide.

## Terms

- **XRechnung**: the German e-invoice standard (XML, EN 16931). Syntaxes: UBL and CII.
- **ZUGFeRD / Factur-X**: a PDF with the invoice XML embedded.
- **EN 16931**: the European semantic model. Fields are numbered business terms (BT-1 is the
  invoice number, BT-109 the net total).
- **KoSIT validator**: the official checker for XRechnung; it returns rule ids such as
  BR-DE-15.
- **§14 UStG**: the German VAT law section that lists what an invoice must contain.
- **§33 UStDV**: lowers those requirements for invoices up to 250 EUR.
- **SKR03**: a standard chart of accounts; the GL (general ledger) coder predicts one.
- **2-way / 3-way match**: invoice against purchase order / against purchase order and goods
  receipt.
- **Risk-coverage curve**: share of invoices booked automatically (coverage) against the share
  of wrong automatic bookings (risk), as the thresholds change. The headline result.

## Reading order for the code

1. `models.py`: the data everything else passes around.
2. `parsing/`: XML and ZUGFeRD to `Invoice`, with evidence.
3. `rules/`: the checks and `engine.py`, which builds the decision.
4. `extraction/`: PDF text, OCR, LLM extraction and the quote check.
5. `synth/`: how test invoices and gold labels are made.
6. Later phases add `ml/`, `pipeline.py`, `evaluate.py`, `agent/`, `api/` and the UI.

## How to run

See the quick start in `README.md`. `make check` runs lint and the unit tests. Integration
tests need the services from `deploy/compose.yaml` (added in phase R0a).

## Sections added by later phases

Each phase appends a short section here: what was added, how to run it, what to look at.
The release checklist (`docs/RELEASE_CHECKLIST.md`) is linked here when A9 writes it.

## Branches and pull requests in this repo

- A **branch** is a movable name that points at a commit. Each commit moves the name forward.
  Each session gets its own branch, so its work stays apart from `main` until I merge it.
- **N ahead, M behind `main`** counts commits: ahead = on the branch but not in `main`, behind =
  in `main` but not on the branch. A new branch starts at the tip of `main`, so behind is 0.
  Behind grows when `main` moves on after the branch was created.
- A **pull request** (PR) asks to bring the commits of one branch into `main` and gives them a
  review page. The PR is not the branch; the branch exists without it.
- **Create a merge commit** adds one commit to `main` with two parents, the old tip of `main`
  and the tip of the branch. Nothing is rewritten.

Example from phase A5. `pranav/a5-agent` (4 commits) and `pranav/r0b-live` (6 commits) both
started at `de3d970`, the tip of `main` after PR #2:

```
                6896c2b - 033283a - 740a376 - dcc73a6   pranav/a5-agent   (PR #3)
               /
... - de3d970 (main)
               \
                bb8f3db - 33a59ba - af8e289 - f2957fd - 50a4482 - 2be45d5   pranav/r0b-live
```

Merging PR #3 created `db86a88` with parents `de3d970` and `dcc73a6`:

```
... - de3d970 ------------------------------------- db86a88 (main)
          \                                        /
           6896c2b - 033283a - 740a376 - dcc73a6
```

After that `pranav/r0b-live` was 6 ahead and 5 behind (the four A5 commits and the merge
commit). I ran `git merge main` on it, which produced `8d8fb57`. Git joined `STATE.md` by
itself; `tests/unit/db/test_db.py` conflicted because both sides added tests at the same
places, and I kept both. Right after the merge it was 7 ahead and 0 behind.

Why the next branch starts from the updated `main`: a branch started from an older branch
carries commits that are already merged, or misses newer ones, and then the same files collide
as here. `pranav/a5-agent` and the cloud copy `claude/a5-agent-implementation-t3sdlm` both end
at `dcc73a6`, which is now in `main`, so either branch can be deleted; its commits stay.
