.PHONY: install test lint type format run

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests

type:
	mypy -p auth

test:
	pytest -m unit
	pytest -m integration
	pytest -m system

check: lint type test

format:
	ruff format src tests
	ruff check src tests --fix

run:
	uvicorn auth.main:app --reload