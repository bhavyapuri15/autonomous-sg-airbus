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
    from backend.ingestion import final_rules_ingest as fri
    if (config.PROCESSED / "final_rule_links.json").exists():
        r = fri.download_pdfs(); print(f"final-rule pdf failures: {len(r['failures'])}")
    print("== build")
    res = build_db.build()
    print("content_sha256", res["content_sha256"], "| inferred verification", res["inferred"], "| build failures", len(res["failures"]))
    print("== page mapping validation")
    v = build_db.validate_page_mapping()
    print(json.dumps({"header_check": {k: x for k, x in v["header_check"].items() if k != "mismatches"},
                      "snippet_overall": v["snippet_check"]["stats"].get("overall"),
                      "snippet_failures": len(v["snippet_check"]["failures"])}, indent=1))
    vf = build_db.validate_page_mapping(out_path=config.PROCESSED / "page_mapping_validation_final_rules.json", source="fr_final_rule_lookup")
    print("final-rule page mapping:", json.dumps({"header": {k: x for k, x in vf["header_check"].items() if k != "mismatches"},
          "snippet_overall": vf["snippet_check"]["stats"].get("overall"), "snippet_failures": len(vf["snippet_check"]["failures"])}))
    cov = build_db.parse_coverage()
    print("== coverage"); print(json.dumps({k: cov[k] for k in ("withdrawals", "c_applicability_paragraphs_with_table", "c_applicability_paragraphs_total")}))
    (config.PROCESSED / "ingest_failures.json").write_text(json.dumps(
        dict(download_failures=dfail, build_failures=res["failures"], parse_coverage=cov), indent=1, sort_keys=True))
    print("== reconcile"); print(json.dumps(reconcile.reconcile()))
    print("== external data manifest")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_manifest
    print(json.dumps(build_manifest.build()["counts"]))
    print("NETWORK_CALLS", dl.NET["calls"])


if __name__ == "__main__":
    main()
