.PHONY: install lint type test-unit test-integration test-system test check format run

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests

type:
	mypy -p auth

test-unit:
	pytest -m unit

test-integration:
	pytest -m integration

test-system:
	pytest -m system

test: test-unit test-integration test-system

check: lint type test

format:
	ruff format src tests
	ruff check src tests --fix

run:
	uvicorn auth.main:app --reload