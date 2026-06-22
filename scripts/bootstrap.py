"""One-shot: create DB schema + seed companies from the source Excel."""
from __future__ import annotations
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from defence_db.db import init_db  # noqa: E402
from defence_db.etl.seed_from_excel import seed  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    n = seed()
    print(f"bootstrap complete — seeded {n} companies")


if __name__ == "__main__":
    main()
