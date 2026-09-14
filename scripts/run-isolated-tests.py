"""Run pytest in a disposable Postgres container; never inherit a product DSN."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def docker_executable():
    configured = os.environ.get("NIS_TEST_DOCKER") or shutil.which("docker")
    fallback = Path.home() / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
    if configured:
        return configured
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError("Docker is required for isolated SQL tests.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685")
    args, tests = parser.parse_known_args()
    if tests[:1] == ["--"]:
        tests = tests[1:]
    docker = docker_executable()
    suffix = secrets.token_hex(6)
    name = "nis-test-db-" + suffix
    database = "nis_test_" + suffix
    password = secrets.token_hex(24)
    environment = {**os.environ, "POSTGRES_PASSWORD": password}
    def call(*command, **kwargs):
        return subprocess.run([docker, *command], check=True, text=True, capture_output=True, env=environment, **kwargs)
    started = False
    try:
        call("run", "-d", "--rm", "--name", name, "--label", "networkis.test=disposable",
             "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_USER=nis_test", "-e", "POSTGRES_DB=" + database,
             "-p", "127.0.0.1::5432", "--tmpfs", "/var/lib/postgresql/data", args.image)
        started = True
        for _ in range(60):
            ready = subprocess.run([docker, "exec", name, "pg_isready", "-U", "nis_test", "-d", database], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Disposable Postgres did not become ready.")
        port = json.loads(call("inspect", name).stdout)[0]["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
        url = f"postgresql://nis_test:{password}@127.0.0.1:{port}/{database}"
        environment.update(DATABASE_URL=url, ENGINEERING_TEST_DATABASE_URL=url, NUMERIC_ACCELERATOR="cpu")
        with tempfile.TemporaryDirectory(prefix="nis-pytest-") as output:
            print(json.dumps({"database": database, "container": name, "isolated": True}), flush=True)
            command = [sys.executable, "-m", "pytest", *(tests or ["backend/tests"]), "-p", "no:cacheprovider", "--basetemp", output]
            return subprocess.run(command, cwd=ROOT, env=environment).returncode
    finally:
        if started:
            subprocess.run([docker, "rm", "-f", name], capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
