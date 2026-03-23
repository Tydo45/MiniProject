import subprocess
import time
import uuid

import pytest
import requests


@pytest.mark.system
def test_container_health():
    postgres_container_name = f"chess-test-postgres-{uuid.uuid4().hex[:8]}"
    network = f"chess-test-network-{uuid.uuid4().hex[:8]}"

    subprocess.run(["docker", "network", "create", network], check=True)

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            postgres_container_name,
            "--network",
            network,
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
            network,
            "-e",
            f"DATABASE_URL=postgresql+psycopg://ci:ci@{postgres_container_name}:5432/ci",
            "-e",
            "SECRET_KEY=ci",
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
            network,
            "-p",
            "8000:8000",
            "-e",
            f"DATABASE_URL=postgresql+psycopg://ci:ci@{postgres_container_name}:5432/ci",
            "-e",
            "SECRET_KEY=ci",
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
        subprocess.run(["docker", "rm", "-f", postgres_container_name], check=False)
        subprocess.run(["docker", "network", "rm", network], check=False)
