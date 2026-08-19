from pathlib import Path

from backend.app.config import BACKEND_ROOT, SIMULATOR_ROOT, backend_root_for


def test_backend_paths_are_relative_to_the_app_package() -> None:
    assert BACKEND_ROOT == Path(__file__).resolve().parents[1]
    assert SIMULATOR_ROOT == BACKEND_ROOT / "simulator"
    assert (SIMULATOR_ROOT / "bus_technologies.py").is_file()


def test_vercel_service_path_resolves_to_var_task() -> None:
    assert backend_root_for("/var/task/app/config.py") == Path("/var/task").resolve()
