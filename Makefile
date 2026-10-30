.PHONY: install lint test fetch

install:
	pip install -e ".[dev,agent,api,ui]"

lint:
	ruff check .

test:
	pytest -m "not integration" -q

fetch:
	python scripts/fetch_data.py
