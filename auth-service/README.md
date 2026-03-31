# Auth Service

[Return to Main Page](../README.md)

FastAPI microservice handling user registration and JWT authentication. Runs on port **8000**.

All other services validate JWTs locally using a shared secret.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | -- | Health check |
| POST | `/user` | -- | Register a new user (returns token pair) |
| POST | `/token` | -- | Login with username/password (returns token pair) |
| POST | `/token/service` | Service token | Exchange a signed service token for a short-lived access token |
| POST | `/refresh` | -- | Refresh an access token using a refresh token |

Tokens are signed with HS256. Access tokens expire after 30 minutes; refresh tokens expire after 7 days.

## Configuration

Copy `.example.env` to `.env`:

```
DATABASE_URL=""                    # PostgreSQL connection string (SQLAlchemy format)
SECRET_KEY=""                      # 256-bit hex key shared with other services for JWT validation
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALLOWED_SERVICES=["chess-service","lobby-service"]  # Services permitted to use /token/service
```

## Development

```bash
make env          # create .venv and install deps
make install      # pip install -e ".[dev]" into active env
make run          # uvicorn with --reload on :8000
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
# installs deps, runs: uvicorn auth_service.main:app --host 0.0.0.0 --port 8000
```

Build and run via the root `docker-compose.yml`:

```bash
make dev    # from repo root
```

Alembic migrations run automatically on container startup (`alembic upgrade head`).

## Database

Uses a dedicated `auth_db` PostgreSQL database. Schema managed by Alembic migrations in `alembic/`.

Tables: `users`.
