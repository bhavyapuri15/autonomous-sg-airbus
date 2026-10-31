"""Cache-first, sequential downloader for FR full_text.xml and govinfo document.pdf.

Writes data/raw/fr_docs/{docnum}/{full_text.xml,document.pdf}; existing files are never
refetched or modified. Failures are returned (and persisted by scripts/ingest.py)."""
import csv, hashlib, json, sys, time
import requests
from backend import config

NET = {"calls": 0}


def sha256_file(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def http_get(url, retries=4):
    last = "no attempt"
    for i in range(retries):
        NET["calls"] += 1
        try:
            r = requests.get(url, headers={"User-Agent": config.HTTP_USER_AGENT}, timeout=90)
            time.sleep(config.HTTP_SLEEP_S)
            if r.status_code == 200:
                return r, None
            last = f"http_{r.status_code}"
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** (i + 1)); continue
            return None, last
        except requests.RequestException as e:
            last = f"neterr_{type(e).__name__}"
            time.sleep(2 ** (i + 1))
    return None, last


def manifest_docnums():
    with open(config.SOURCE_MANIFEST, newline="") as f:
        return sorted({r["docnum"] for r in csv.DictReader(f) if r["fr_fetch_status"] == "ok" and r["docnum"]})


def load_metadata(docnum):
    return json.loads((config.FR_METADATA_DIR / f"{docnum}.json").read_text())


def download_all(docnums=None, log=print):
    """Returns (failures: list[dict], sha: dict docnum->{xml,pdf}). Idempotent."""
    docnums = docnums or manifest_docnums()
    failures = []
    for n, docnum in enumerate(docnums, 1):
        meta = load_metadata(docnum)
        d = config.FR_DOCS_DIR / docnum
        d.mkdir(parents=True, exist_ok=True)
        for url_key, name in (("full_text_xml_url", "full_text.xml"), ("pdf_url", "document.pdf")):
            p = d / name
            if p.exists() and p.stat().st_size > 0:
                continue
            url = meta.get(url_key)
            if not url:
                failures.append(dict(fr_docnum=docnum, file=name, reason="no_url_in_metadata")); continue
            r, err = http_get(url)
            if r is None:
                failures.append(dict(fr_docnum=docnum, file=name, url=url, reason=err)); continue
            p.write_bytes(r.content)
        if n % 25 == 0:
            log(f"  downloaded {n}/{len(docnums)} (net calls {NET['calls']})", file=sys.stderr)
    # failures that persist = files still missing
    failures = [f for f in failures if not (config.FR_DOCS_DIR / f["fr_docnum"] / f["file"]).exists()]
    return failures


if __name__ == "__main__":
    fl = download_all()
    print("failures", len(fl), "network_calls", NET["calls"])
