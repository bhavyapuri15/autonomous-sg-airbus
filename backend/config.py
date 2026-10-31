"""Central paths and constants. All other modules import locations from here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
INDEXES = DATA / "indexes"

SHEET_XLSX = RAW / "sheet_snapshot" / "dataset.xlsx"
SHEET_SHA256 = "3bc255f5f790b3adf41b8b70525dd1867310820801ac960fedf9b3ddc2fb1fd0"

FR_METADATA_DIR = RAW / "fr_metadata"   # {docnum}.json from FR API
FR_DOCS_DIR = RAW / "fr_docs"           # {docnum}/full_text.xml, document.pdf
FR_FINAL_RULES_DIR = RAW / "fr_final_rules"
SOURCE_MANIFEST = PROCESSED / "source_manifest.csv"

DB_PATH = INDEXES / "ad.sqlite"

FR_API = "https://www.federalregister.gov/api/v1"
HTTP_USER_AGENT = "autonomous-sg-airbus-hackathon-prototype/0.1 (research; contact via repo)"
HTTP_SLEEP_S = 0.5
