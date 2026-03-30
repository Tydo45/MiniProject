# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A chess game application built as microservices: three FastAPI Python backends + a React/TypeScript frontend. Services communicate via HTTP and WebSockets; matchmaking calls chess service to create games.

```
Frontend (React/Vite :5173)
  ↓ HTTP + WebSocket
├── Auth Service (FastAPI :8000) — JWT auth, user management
├── Lobby Service (FastAPI :8001) — invites, matchmaking → calls Chess Service
└── Chess Service (FastAPI :8002) — game logic, moves (uses python-chess)
         ↓
    PostgreSQL (3 separate databases: auth_db, lobby_db, chess_db)
```

## Commands

### Full Stack (Docker)
```bash
make dev          # docker compose up --build
make down         # docker compose down
make logs         # docker compose logs -f
```

### Python Services (auth-service, lobby-service, chess-service)
Each service has an identical Makefile interface:
```bash
make install      # pip install -e ".[dev]"
make run          # uvicorn <service>.main:app --reload
make lint         # ruff check
make format       # ruff format
make type         # mypy
make test-unit    # pytest -m unit
make test-integration  # pytest -m integration
make test-system  # pytest -m system
make check        # lint + type + all tests
```

### Frontend
```bash
cd frontend
npm install
npm run dev       # vite dev server with HMR
npm run build     # tsc -b && vite build
npm run lint      # eslint .
```

### Running a Single Test
```bash
cd <service>
pytest tests/unit/test_foo.py::test_specific_function
pytest -m unit -k "test_name_pattern"
```

## Architecture

### Python Services
All three services share the same layout:
- `src/<service>/main.py` — FastAPI app, CORS, router registration
- `src/<service>/routes/routes.py` — endpoint handlers
- `src/<service>/models.py` — SQLAlchemy ORM models
- `src/<service>/api_models.py` — Pydantic request/response schemas
- `alembic/` — database migrations (run on container startup via `alembic upgrade head`)
- `tests/{unit,integration,system}/` — 3-tier tests

**Auth tokens**: PyJWT with HS256. All lobby/chess endpoints require `Authorization: Bearer <token>`. The lobby service validates JWTs locally (shared secret); it does not call the auth service on each request.

**Inter-service calls**: Lobby service calls Chess Service at `http://chess-service:8002` (docker hostname) to create games. `httpx` is used for async HTTP.

**WebSockets**: Both lobby and chess services have WebSocket routers for real-time event delivery (invites/ready signals and move notifications).

### Frontend
- `src/App.tsx` — React Router setup with `ProtectedRoute` wrapper
- `src/api/` — typed API clients per service
- `src/context/` — React context providers
- `src/types/` — shared TypeScript types
- JWT stored in `localStorage`; services contacted at `http://localhost:{8000,8001,8002}`

### Database
Single PostgreSQL instance; three databases created by `/postgres/init/01-create-service-dbs.sql`. Each service connects to its own database via `DATABASE_URL` env var.

## Configuration

Each Python service reads from a `.env` file. Required variables:
- `DATABASE_URL` — PostgreSQL connection string (SQLAlchemy format)
- `SECRET_KEY` — JWT signing key (shared across services for token validation)

CI uses:
```
DATABASE_URL=postgresql+psycopg://ci:ci@localhost:5432/ci
SECRET_KEY=fake_jwt_secret_key_for_testing_only_7f3a1c9d4e8b2a6f0c1d9e7a5b3c8d2e
```

## Code Quality

- **Ruff**: linting and formatting (configured in `pyproject.toml`)
- **MyPy**: strict mode enabled; all functions must be typed
- **pytest markers**: `unit`, `integration`, `system` — integration tests require a live database
- GitHub Actions runs the full `make check` pipeline on each service when its paths change
