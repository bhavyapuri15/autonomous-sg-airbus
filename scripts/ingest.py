#!/usr/bin/env python3
"""Task 1 ingestion CLI: download -> build DB -> validate page mapping -> coverage -> reconcile. Idempotent; cache-first."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config
from backend.ingestion import document_downloader as dl, build_db, reconcile


def main():
    config.INDEXES.mkdir(parents=True, exist_ok=True); config.PROCESSED.mkdir(parents=True, exist_ok=True)
    print("== download")
    dfail = dl.download_all()
    print(f"download failures: {len(dfail)}; network calls: {dl.NET['calls']}")
    print("== build")
    res = build_db.build()
    print("content_sha256", res["content_sha256"], "| inferred verification", res["inferred"], "| build failures", len(res["failures"]))
    print("== page mapping validation")
    v = build_db.validate_page_mapping()
    print(json.dumps({"header_check": {k: x for k, x in v["header_check"].items() if k != "mismatches"},
                      "snippet_overall": v["snippet_check"]["stats"].get("overall"),
                      "snippet_failures": len(v["snippet_check"]["failures"])}, indent=1))
    cov = build_db.parse_coverage()
    print("== coverage"); print(json.dumps({k: cov[k] for k in ("withdrawals", "c_applicability_paragraphs_with_table", "c_applicability_paragraphs_total")}))
    (config.PROCESSED / "ingest_failures.json").write_text(json.dumps(
        dict(download_failures=dfail, build_failures=res["failures"], parse_coverage=cov), indent=1, sort_keys=True))
    print("== reconcile"); print(json.dumps(reconcile.reconcile()))
    print("NETWORK_CALLS", dl.NET["calls"])


if __name__ == "__main__":
    main()
