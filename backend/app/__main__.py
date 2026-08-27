"""Development entry point for the Flask API."""

from __future__ import annotations

import os
import socket
import sys

from werkzeug.serving import ThreadedWSGIServer

from . import create_app
from .runtime_config import runtime_settings


class ExclusiveThreadedWSGIServer(ThreadedWSGIServer):
    """Threaded development server which never shares its listening port."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        # On Windows SO_REUSEADDR may let a second process steal traffic from an
        # existing listener.  EXCLUSIVEADDRUSE makes ownership unambiguous.
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _server_settings() -> tuple[str, int, bool]:
    host = os.environ.get("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
    raw_port = os.environ.get("FLASK_PORT", "15050").strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise SystemExit(f"Ungültiger FLASK_PORT: {raw_port!r}") from error
    if not 1 <= port <= 65535:
        raise SystemExit(f"FLASK_PORT muss zwischen 1 und 65535 liegen: {port}")
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    return host, port, debug


def main() -> int:
    host, port, debug = _server_settings()
    app = create_app()
    app.debug = debug
    if not debug:
        try:
            from waitress import serve
        except ImportError as error:
            raise SystemExit(
                "Waitress ist nicht installiert. Führe `uv sync --project backend` aus."
            ) from error
        settings = runtime_settings()
        os.environ["SIMULATOR_SERVER"] = "waitress"
        print(
            f"Simulator-Backend via Waitress auf http://{host}:{port} "
            f"({settings.api_threads} Threads, {settings.simulation_workers} Worker)",
            flush=True,
        )
        try:
            serve(
                app,
                host=host,
                port=port,
                threads=settings.api_threads,
                clear_untrusted_proxy_headers=True,
            )
        except OSError as error:
            print(
                f"Simulator-Backend nicht gestartet: {host}:{port} ist bereits belegt.",
                file=sys.stderr,
            )
            return 2
        return 0

    os.environ["SIMULATOR_SERVER"] = "werkzeug"
    try:
        server = ExclusiveThreadedWSGIServer(host, port, app)
    except SystemExit:
        print(
            f"Simulator-Backend nicht gestartet: {host}:{port} ist bereits belegt. "
            "Der Port wird nicht automatisch gewechselt.",
            file=sys.stderr,
        )
        return 2

    print(f"Simulator-Backend exklusiv auf http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
