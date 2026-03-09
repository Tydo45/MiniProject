import subprocess
import time

import pytest
import requests


@pytest.mark.system
def test_container_health():
    subprocess.run(["docker", "network", "create", "chess-test-network"], check=True)

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "chess-test-postgres",
            "--network",
            "chess-test-network",
            "-e",
            "POSTGRES_DB=ci",
            "-e",
            "POSTGRES_USER=ci",
            "-e",
            "POSTGRES_PASSWORD=ci",
            "postgres:16",
        ],
        check=True,
    )

    time.sleep(5)

    subprocess.run(["docker", "build", "-t", "chess-test", "."], check=True)

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "chess-test-network",
            "-e",
            "DATABASE_URL=postgresql+psycopg://ci:ci@chess-test-postgres:5432/ci",
            "chess-test",
            "alembic",
            "upgrade",
            "head",
        ],
        check=True,
    )

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "chess-test",
            "--network",
            "chess-test-network",
            "-p",
            "8000:8000",
            "-e",
            "DATABASE_URL=postgresql+psycopg://ci:ci@chess-test-postgres:5432/ci",
            "chess-test",
        ],
        check=True,
    )

    try:
        time.sleep(5)

        response = requests.get("http://localhost:8000/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    finally:
        subprocess.run(["docker", "rm", "-f", "chess-test"], check=False)
        subprocess.run(["docker", "rm", "-f", "chess-test-postgres"], check=False)
        subprocess.run(["docker", "network", "rm", "chess-test-network"], check=False)
