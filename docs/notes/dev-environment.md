# Dev environment

What it does: a fresh clone gets the same Python, tesseract with German data, pinned packages,
Postgres with pgvector and KoSIT validator, with `make up` and "Reopen in Container". Commands
(`make check`, `make test-integration`) run inside the `dev` container.

How it works: `deploy/compose.yaml` has three services in the profile `core`. `dev` is built
from `deploy/docker/Dockerfile` (python 3.12 slim, tesseract-ocr-deu, packages from
`requirements.lock`, the project installed editable, repo mounted at `/workspace`); it gets
`DATABASE_URL` and `VALIDATOR_URL` pointing at the other services and starts only when both
are healthy. `postgres` is `pgvector/pgvector:pg16`. `validator` is built from
`deploy/docker/validator.Dockerfile`: Temurin 21 JRE, the pinned standalone jar and the
XRechnung configuration from `DATA_SOURCES.md`, daemon on port 8081. `make lock` resolves
`pyproject.toml` in a clean container, installs torch from the PyTorch CPU index first, and
writes `pip freeze` plus the CPU index line to `requirements.lock`.

Why this way: one image for dev and later api and ui, so tests run on what is shipped. The lock
is a plain `pip freeze` because the project already pins with `~=` and a second resolver
(uv, pip-tools) would be a new dependency for a file that changes rarely. The container user
has uid 1000, so files written into the mounted repo stay editable on the host; root-owned
`.pytest_cache` and `data/synth` would not. Ports are bound to localhost and the database
password exists only in this Compose file.

How it is tested: `make check` (213 passed, the two OCR tests now run) and `make
test-integration` (the validator accepts a testsuite invoice) pass inside the container started
by `make up` and by the devcontainer CLI (`devcontainer up`, `devcontainer exec`). Postgres
answers from the dev container and has the `vector` extension available. They do not prove that
VS Code's "Reopen in Container" button works; the CLI reads the same file.

Limits: the validator and configuration are downloaded without a checksum. `dev` carries the
test and lint tools, so the future api image is larger than needed. The lock is for linux/amd64
only. Postgres migrations have not been run against this database yet (R0b).
