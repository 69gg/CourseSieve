from __future__ import annotations

import logging
from rich.logging import RichHandler


_LOG_FORMAT = "%(message)s"


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
