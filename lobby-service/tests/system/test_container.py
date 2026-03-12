import subprocess
import time

import pytest
import requests


@pytest.mark.system
def test_container_health():
    subprocess.run(["docker", "network", "create", "lobby-test-network"], check=True)

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "lobby-test-postgres",
            "--network",
            "lobby-test-network",
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

    subprocess.run(["docker", "build", "-t", "lobby-test", "."], check=True)

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "lobby-test-network",
            "-e",
            "DATABASE_URL=postgresql+psycopg://ci:ci@lobby-test-postgres:5432/ci",
            "-e",
            "SECRET_KEY=ci",
            "lobby-test",
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
            "lobby-test",
            "--network",
            "lobby-test-network",
            "-p",
            "8000:8000",
            "-e",
            "DATABASE_URL=postgresql+psycopg://ci:ci@lobby-test-postgres:5432/ci",
            "-e",
            "SECRET_KEY=ci",
            "lobby-test",
        ],
        check=True,
    )

    try:
        time.sleep(5)

        response = requests.get("http://localhost:8000/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    finally:
        subprocess.run(["docker", "rm", "-f", "lobby-test"], check=False)
        subprocess.run(["docker", "rm", "-f", "lobby-test-postgres"], check=False)
        subprocess.run(["docker", "network", "rm", "lobby-test-network"], check=False)
