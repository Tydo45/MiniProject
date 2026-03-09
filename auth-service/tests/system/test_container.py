import subprocess
import time

import pytest
import requests


@pytest.mark.system
def test_container_health():
    subprocess.run(["docker", "build", "-t", "auth-test", "."], check=True)

    subprocess.run(
        ["docker", "run", "-d", "-p", "8000:8000", "--name", "auth-test", "auth-test"],
        check=True,
    )

    try:
        time.sleep(3)

        response = requests.get("http://localhost:8000/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    finally:
        subprocess.run(["docker", "rm", "-f", "auth-test"], check=False)
