"""Development entry point for the Flask API."""

from __future__ import annotations

import os

from . import create_app


def main() -> None:
    app = create_app()
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5050")),
        debug=os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"},
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
