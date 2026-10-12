.PHONY: install check lint test

install:
	pip install -e ".[all,dev]"

lint:
	ruff check .

test:
	pytest

# What CI runs
check: lint test
