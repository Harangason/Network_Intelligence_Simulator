"""Cooperative, attempt-local cancellation shared by thread and spawn workers."""
from contextlib import contextmanager
from contextvars import ContextVar
from concurrent.futures import CancelledError
from pathlib import Path
from time import monotonic


_active_check = ContextVar('simulation_cancellation_check', default=None)
_MARKER = '.cancellation-requested'


def cancellation_requested(output_dir):
    return (Path(output_dir) / _MARKER).exists()


def request_cancellation(output_dir):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / _MARKER).touch(exist_ok=True)


@contextmanager
def cancellation_scope(output_dir):
    marker = Path(output_dir) / _MARKER
    next_poll = 0.0

    def check(force=False):
        nonlocal next_poll
        now = monotonic()
        if force or now >= next_poll:
            next_poll = now + 0.05
            if marker.exists():
                raise CancelledError('Simulation wurde abgebrochen.')

    token = _active_check.set(check)
    try:
        check(force=True)
        yield
        check(force=True)
    finally:
        _active_check.reset(token)


def check_cancellation(*, force=False):
    check = _active_check.get()
    if check is not None:
        check(force=force)
