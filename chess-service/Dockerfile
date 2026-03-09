FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic ./alembic
COPY src ./src

RUN pip install .

CMD ["uvicorn", "chess.main:app", "--host", "0.0.0.0", "--port", "8000"]