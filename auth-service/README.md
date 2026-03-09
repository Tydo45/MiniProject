# Auth Micro-Service

## Environment Variables

- `DATABASE_URL` (required): primary SQLAlchemy connection URL.
- `TEST_DATABASE_URL` (optional): integration test DB URL. If unset, tests fall back to
  `DATABASE_URL`.

### Local Development

1. Copy `.env.example` to `.env`.
2. Set `DATABASE_URL` for your local database.

The service and Alembic load `.env` in their entrypoints for local convenience. Container and
CI environments should continue to pass environment variables explicitly.
