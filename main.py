"""Paper Notes — Academic Paper Management Application.

Native desktop app — fast, no browser, direct database access.
"""

import logging

from ui.tk_app import TkApp
from utils.logger import setup_logging


def main() -> None:
    """Launch the native desktop application."""
    setup_logging(level=logging.INFO)
    app = TkApp()
    app.run()


if __name__ == "__main__":
    main()
