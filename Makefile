COMPOSE = docker compose -f deploy/compose.yaml --profile core

.PHONY: lint test check test-integration fetch up down lock

# lint, test, check, test-integration and fetch run inside the dev container.
lint:
	ruff check .

test:
	pytest -m "not integration" -q

check: lint test

test-integration:
	pytest -m integration -q

fetch:
	python scripts/fetch_data.py

# up, down and lock run on the host.
up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

# Resolves pyproject.toml in a clean container with the PyTorch CPU wheels first (the default
# wheels bring CUDA) and writes the result next to the CPU index line pip needs to read it.
lock:
	docker run --rm -v "$(CURDIR)":/src:ro python:3.12-slim sh -ec '\
		mkdir /tmp/p && cp -r /src/pyproject.toml /src/README.md /src/LICENSE /src/src /tmp/p && \
		python -m venv /tmp/venv && . /tmp/venv/bin/activate && \
		pip install -q --index-url https://download.pytorch.org/whl/cpu torch >&2 && \
		pip install -q "/tmp/p[dev,agent,api,ui]" >&2 && \
		echo "--extra-index-url https://download.pytorch.org/whl/cpu" && \
		pip freeze --exclude einvoice' > requirements.lock.tmp
	mv requirements.lock.tmp requirements.lock
