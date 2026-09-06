"""Thread-safe cancellation of this server's active wizard tasks."""
import asyncio
import threading

_lock = threading.Lock()
_runs = {}


class RunCancellation:
    def __init__(self, project_id, wizard_run_id):
        self.key = (project_id, wizard_run_id)
        self.cancelled = threading.Event()
        self.loop = self.task = None
        with _lock:
            _runs[self.key] = self

    def bind(self):
        with _lock:
            self.loop, self.task = asyncio.get_running_loop(), asyncio.current_task()
        self.check()

    def check(self):
        if self.cancelled.is_set():
            raise asyncio.CancelledError()

    def close(self):
        with _lock:
            if _runs.get(self.key) is self:
                del _runs[self.key]


def request_cancel(project_id, wizard_run_id):
    with _lock:
        control = _runs.get((project_id, wizard_run_id))
        if control:
            control.cancelled.set()
            if control.loop and not control.loop.is_closed():
                control.loop.call_soon_threadsafe(control.task.cancel)
    return control is not None
