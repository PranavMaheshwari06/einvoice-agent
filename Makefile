.PHONY: install lint test check fetch

install:
	pip install -e ".[dev,agent,api,ui]"

lint:
	ruff check .

test:
	pytest -m "not integration" -q

check: lint test

fetch:
	python scripts/fetch_data.py
