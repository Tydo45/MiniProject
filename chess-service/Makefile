.PHONY: install lint type test-unit test-integration test-system test check format run test-cov-report

install:
	pip install -e ".[dev]"

env:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e ".[dev]"

lint:
	ruff check src tests

type:
	mypy -p chess_service

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
	uvicorn chess_service.main:app --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf \
		.pytest_cache \
		.mypy_cache \
		.ruff_cache \
		.coverage \
		build \
		dist

test-cov-report:
	pytest --cov=. --cov-branch --cov-report=html
	explorer.exe "$$(wslpath -w htmlcov/index.html)"