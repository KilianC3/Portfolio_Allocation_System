import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from service.logger import get_logger
from service.start import main as start_main

_log = get_logger("bootstrap")


def main() -> None:
    _log.info("bootstrap begin")
    asyncio.run(start_main())


if __name__ == "__main__":
    main()
