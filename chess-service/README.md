# Chess Service

[Return to Main Page](../README.md)

FastAPI microservice handling chess game logic. Runs on port **8002**.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | -- | Health check |
| POST | `/games` | JWT | List user's active games |
| POST | `/games/create` | Service token | Create a game (lobby → chess only) |
| POST | `/games/{id}/move` | JWT | Submit a move (UCI format) |
| POST | `/games/{id}/draw` | JWT | Offer a draw |
| POST | `/games/{id}/draw/accept` | JWT | Accept a draw offer |
| POST | `/games/{id}/draw/decline` | JWT | Decline a draw offer |
| POST | `/games/{id}/resign` | JWT | Resign from a game |
| WS | `/ws/{user_id}` | -- | WebSocket for real-time game events |

Move validation uses [`python-chess`](https://python-chess.readthedocs.io/). Moves are submitted in [UCI format](https://en.wikipedia.org/wiki/Universal_Chess_Interface) (e.g. `e2e4`).

WebSocket events pushed to players: `game_updated`, `draw_proposed`, `draw_accepted`, `draw_declined`, `opponent_resigned`.

## Configuration

Copy `.example.env` to `.env`:

```
DATABASE_URL=""   # PostgreSQL connection string (SQLAlchemy format)
SECRET_KEY=""     # 256-bit hex key shared with other services for JWT validation
ALGORITHM="HS256"
```

## Development

```bash
make env          # create .venv and install deps
make install      # pip install -e ".[dev]" into active env
make run          # uvicorn with --reload on :8002
```

## Testing

```bash
make test-unit         # unit tests (no DB required)
make test-integration  # integration tests (requires live DB)
make test-system       # system/container tests
make test              # all three
```

Integration tests expect a PostgreSQL instance, this is created with Docker making Docker a dependency. CI uses:
```
DATABASE_URL=postgresql+psycopg://ci:ci@localhost:5432/ci
```

## Linting & Formatting

```bash
make lint     # ruff check
make format   # ruff format + ruff check --fix
make type     # mypy (strict mode)
make check    # lint + type + all tests
```

Ruff is configured for line length 100, targeting Python 3.11. MyPy runs in strict mode.

## Docker

```dockerfile
FROM python:3.11-slim
# installs deps, runs: uvicorn chess_service.main:app --host 0.0.0.0 --port 8002
```

Build and run via the root `docker-compose.yml`:

```bash
make dev    # from repo root
```

Alembic migrations run automatically on container startup (`alembic upgrade head`).

## Database

Uses a dedicated `chess_db` PostgreSQL database. Schema managed by Alembic migrations in `alembic/`.

Tables: `games`, `game_events`.

Models defined in ```src/chess-service/models.py```