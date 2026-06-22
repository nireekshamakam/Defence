"""Nightly refresh entry-point — pulls latest market data and writes an Excel export."""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from defence_db.db import init_db  # noqa: E402
from defence_db.etl.refresh_market import refresh_all  # noqa: E402
from defence_db.etl.export_excel import export  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Refresh defence DB and export Excel snapshot")
    p.add_argument("--skip-export", action="store_true", help="don't write an .xlsx after refresh")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    r = refresh_all()
    print(f"refreshed {r.companies_succeeded}/{r.companies_attempted} companies via {r.source}")
    if not args.skip_export:
        path = export()
        print(f"export written to {path}")


if __name__ == "__main__":
    main()
