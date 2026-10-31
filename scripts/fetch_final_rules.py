"""Build data/processed/final_rule_links.json (O1). Prints stats and a network-call counter."""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.ingestion import final_rules as fr  # noqa: E402


def main():
    res = fr.run()
    st = res["_stats"]
    print("dockets queried:", st["dockets"], "| discarded fuzzy hits:", st["discarded"])
    print("NETWORK CALLS:", st["network_calls"])
    print("rules by class:", dict(collections.Counter(r["doc_class"] for r in res["rules"])))
    docs = {d["docnum"]: d for d in res["_docs"]}
    c = collections.Counter()
    for l in res["links"]:
        mod = "modern" if docs[l["dataset_docnum"]]["publication_date"][:4] >= str(fr.MODERN_YEAR) else "legacy"
        c[(l["status"], mod)] += 1
    for d in res["dataset_docs_without_rules"]:
        mod = "modern" if docs[d]["publication_date"][:4] >= str(fr.MODERN_YEAR) else "legacy"
        c[("NO_FINAL_RULE_FOUND_IN_FR", mod)] += 1
    for k in sorted(c):
        print("link status", k, c[k])
    fin = [r for r in res["rules"] if r["doc_class"].startswith("FINAL")]
    print("final rules:", len(fin), "ad_number found:", sum(1 for r in fin if r["ad_number"]),
          "amendment found:", sum(1 for r in fin if r["amendment"]),
          "with supersedes:", sum(1 for r in fin if r["supersedes"]),
          "no xml:", sum(1 for r in res["rules"] if not r["xml_sha256"]))


if __name__ == "__main__":
    main()
