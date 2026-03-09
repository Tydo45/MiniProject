import subprocess
import time

import pytest
import requests

from auth.config import get_settings


@pytest.mark.system
def test_container_health():
    settings = get_settings()

    subprocess.run(["docker", "network", "create", "auth-test-network"], check=True)

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "auth-test-postgres",
            "--network",
            "auth-test-network",
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

    subprocess.run(["docker", "build", "-t", "auth-test", "."], check=True)

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "auth-test-network",
            "-e",
            "DATABASE_URL=postgresql+psycopg://ci:ci@auth-test-postgres:5432/ci",
            "-e",
            f"SECRET_KEY={settings.secret_key}",
            "auth-test",
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
            "auth-test",
            "--network",
            "auth-test-network",
            "-p",
            "8000:8000",
            "-e",
            "DATABASE_URL=postgresql+psycopg://ci:ci@auth-test-postgres:5432/ci",
            "-e",
            f"SECRET_KEY={settings.secret_key}",
            "auth-test",
        ],
        check=True,
    )

    try:
        time.sleep(5)

        response = requests.get("http://localhost:8000/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    finally:
        subprocess.run(["docker", "rm", "-f", "auth-test"], check=False)
        subprocess.run(["docker", "rm", "-f", "auth-test-postgres"], check=False)
        subprocess.run(["docker", "network", "rm", "auth-test-network"], check=False)
