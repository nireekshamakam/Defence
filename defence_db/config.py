from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EXPORT_DIR = DATA_DIR / "exports"
SOURCE_EXCEL = DATA_DIR / "source_excel" / "20260212_Defence_Companies_Database_vNM.xlsx"

DB_URL = os.environ.get("DEFENCE_DB_URL", f"sqlite:///{DATA_DIR / 'defence.db'}")

INR_PER_USD_FALLBACK = float(os.environ.get("INR_PER_USD", "83.5"))

EXPORT_DIR.mkdir(parents=True, exist_ok=True)
