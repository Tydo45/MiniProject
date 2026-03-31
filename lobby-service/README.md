# Lobby Service

[Return to Main Page](../README.md)

FastAPI microservice handling invites, open lobbies, and matchmaking. Runs on port **8001**.

When both players ready up, the lobby service calls the chess service to create a game.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | -- | Health check |
| GET | `/open-lobbies` | JWT | List all open lobbies |
| POST | `/open-lobbies` | JWT | Create an open lobby (joinable by anyone) |
| GET | `/open-lobbies/join/{lobby_id}` | JWT | Join an open lobby |
| GET | `/invites` | JWT | List incoming invites for the requesting user |
| POST | `/invites/send` | JWT | Send a game invite to another player |
| POST | `/invites/accept` | JWT | Accept a game invite (creates a lobby) |
| POST | `/ready` | JWT | Mark yourself ready in a lobby; triggers game creation when both players are ready |
| WS | `/ws` | JWT | WebSocket for real-time lobby events |

WebSocket events pushed to players: `open_join`, `invite_created`, `invite_accepted`, `user_ready`.

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
make run          # uvicorn with --reload on :8001
```

## Testing

```bash
make test-unit         # unit tests (no DB required)
make test-integration  # integration tests (requires live DB)
make test-system       # system/container tests
make test              # all three
```

Integration tests expect a PostgreSQL instance. CI uses:
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
# installs deps, runs: uvicorn lobby_service.main:app --host 0.0.0.0 --port 8001
```

Build and run via the root `docker-compose.yml`:

```bash
make dev    # from repo root
```

Alembic migrations run automatically on container startup (`alembic upgrade head`).

## Database

Uses a dedicated `lobby_db` PostgreSQL database. Schema managed by Alembic migrations in `alembic/`.

Tables: `invites`, `open_lobbies`, `lobbies`.
