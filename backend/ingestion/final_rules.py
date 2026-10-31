"""O1: verified final-rule lookup for FAA AD proposed rules (traceable, evidence-first)."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from lxml import etree

from backend import config

SEARCH_FIELDS = ["document_number", "title", "type", "action", "publication_date", "citation",
                 "docket_ids", "effective_on", "full_text_xml_url", "pdf_url", "html_url",
                 "correction_of", "regulation_id_numbers"]
MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December")
MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTHS.split("|"))}
MODERN_YEAR = 2021


# ----------------------------------------------------------------- normalization
_PREFIX = re.compile(r"^(?:docket\s*(?:no\.?|number|id)?|(?:project|product|directorate)\s+identifier"
                     r"|faa\s+rules)\s*[:.]?\s*", re.I)


def normalize_dockets(raw) -> list[str]:
    """Normalize FR docket_ids entries to bare identifiers. Drops 'Amendment ..' / 'AD ..' entries."""
    if isinstance(raw, str):
        raw = [raw]
    out = []
    for item in raw or []:
        for tok in re.split(r"[;,]|\s+and\s+|\s+(?=(?:project|product|directorate)\s+identifier)", item or "", flags=re.I):
            t = " ".join(tok.split())
            if not t or re.match(r"^(amendment|ad)\s+\d", t, re.I):
                continue
            t = _PREFIX.sub("", t).strip(" .")
            m = re.match(r"^FAA[\s-]+(\d{4}-\d+)$", t, re.I)
            if m:
                t = "FAA-" + m.group(1)
            t = t.upper()
            if t and t not in out:
                out.append(t)
    return out


def docket_key(d: str) -> str:
    """Comparison key: legacy ids sometimes omit the trailing -AD."""
    return re.sub(r"-AD$", "", d.upper())


def shared_dockets(a: list[str], b: list[str]) -> list[str]:
    kb = {docket_key(x) for x in b}
    return sorted({x for x in a if docket_key(x) in kb})


def doc_class(action: str) -> str:
    a = (action or "").lower()
    if "withdraw" in a:
        return "WITHDRAWAL"
    if "supplemental" in a:
        return "SNPRM"
    if "correct" in a:
        return "CORRECTION"
    if "proposed rule" in a or "notice of proposed rulemaking" in a:
        return "NPRM"
    return "OTHER"


def classify_rule(doc: dict) -> str:
    action = (doc.get("action") or "").lower()
    title = (doc.get("title") or "")
    if "correction" in action:
        return "CORRECTION"
    if doc.get("type") == "Rule" and title.startswith("Airworthiness Directives"):
        if "request for comments" in action or "immediately adopted" in action:
            return "FINAL_RULE_REQUEST_FOR_COMMENTS"
        if "final rule" in action:
            return "FINAL_RULE"
    return "OTHER_RULE"


# ----------------------------------------------------------------- text + evidence
BLOCK = {"P", "FP", "HD", "AMDPAR", "SECTNO", "SUBJECT", "LI", "AUTH", "DEPDOC"}


def normalized_text(xml_bytes: bytes) -> str:
    """Whitespace-collapsed paragraphs joined by blank lines (tables skipped)."""
    root = etree.fromstring(xml_bytes)
    paras = []
    for el in root.iter():
        if not isinstance(el.tag, str) or el.tag not in BLOCK:
            continue
        if any(isinstance(a.tag, str) and (a.tag in BLOCK or a.tag == "GPOTABLE") for a in el.iterancestors()):
            continue
        t = " ".join("".join(el.itertext()).split())
        if t:
            paras.append(t)
    return "\n\n".join(paras)


def _span(text, m, group=0):
    s, e = m.start(group), m.end(group)
    return {"quote": text[s:e], "start": s, "end": e}


AD_HEAD = re.compile(r"(?m)^(\d{2,4}-\d{2}-\d{2})\s[^\n]*?:\s*Amendment\s+39-\d+")


def extract_ad_amendment(text: str):
    m = AD_HEAD.search(text)
    if not m:
        return None, None
    ad = {"value": m.group(1), **_span(text, m, 1)}
    am = re.search(r"Amendment\s+39-\d+", text[m.start():m.end()])
    amend = None
    if am:
        s = m.start() + am.start()
        e = m.start() + am.end()
        amend = {"value": text[s:e].split()[-1], "quote": text[s:e], "start": s, "end": e}
    return ad, amend


_SUP = re.compile(r"\b(supersedes|superseding|removing|removes|rescinds|rescinding)\s+"
                  r"(?:and replacing\s+)?(?:Airworthiness Directive(?:s)?\s*(?:\(ADs?\))?|ADs?)\s+"
                  r"(\d{2,4}-\d{2}-\d{2})((?:\s*(?:,|and)\s*(?:AD\s+)?\d{2,4}-\d{2}-\d{2})*)", re.I)


def extract_supersedes(text: str) -> list[dict]:
    out = []
    for m in _SUP.finditer(text):
        nums = [m.group(2)] + re.findall(r"\d{2,4}-\d{2}-\d{2}", m.group(3) or "")
        for n in nums:
            out.append({"ad_number": n, "quote": text[m.start():m.end()], "start": m.start(), "end": m.end()})
    return out


_CIT = re.compile(r"\b(\d{1,3}) FR (\d{1,6})\b")
_DATE = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})\b")
_CTX = re.compile(r"NPRM|SNPRM|proposed|supplemental|notice of proposed", re.I)


def extract_citations(text: str):
    return [{"citation": f"{m.group(1)} FR {m.group(2)}", **_span(text, m)} for m in _CIT.finditer(text)]


def extract_dates(text: str, window: int = 200):
    """Dates written 'Month D, YYYY' that have NPRM/proposed context within `window` chars."""
    out = []
    for m in _DATE.finditer(text):
        ctx = text[max(0, m.start() - window): m.end() + window]
        if _CTX.search(ctx):
            iso = f"{m.group(3)}-{MONTH_NUM[m.group(1)]:02d}-{int(m.group(2)):02d}"
            out.append({"date": iso, **_span(text, m)})
    return out


def find_backrefs(text: str, doc: dict, conflicts: list | None = None) -> list[dict]:
    """Evidence that the rule text refers to this specific dataset doc."""
    ev = []
    for c in extract_citations(text):
        if c["citation"] == doc["citation"]:
            ctx = text[max(0, c["start"] - 200): c["end"] + 200]
            if _CTX.search(ctx):
                ev.append({"type": "nprm_citation", "quote": c["quote"], "start": c["start"], "end": c["end"]})
    for d in extract_dates(text):
        if d["date"] == doc["publication_date"]:
            near = [c["citation"] for c in extract_citations(text[max(0, d["start"] - 60): d["end"] + 60])]
            if any(c != doc["citation"] for c in near) and doc["citation"] not in near:
                # same date but the adjacent FR citation differs: do not trust (possible typo / other doc)
                if conflicts is not None:
                    conflicts.append(f"date {d['quote']} matches but adjacent citation {near} != {doc['citation']}")
                continue
            ev.append({"type": "nprm_date", "quote": d["quote"], "start": d["start"], "end": d["end"]})
    uniq, seen = [], set()
    for e in sorted(ev, key=lambda e: (e["start"], e["type"])):
        if (e["type"], e["quote"]) not in seen:  # keep first occurrence of each distinct quote
            seen.add((e["type"], e["quote"]))
            uniq.append(e)
    return uniq


def decide_status(doc: dict, rule: dict, evidence: list[dict]):
    """Status decision table. Returns (status, notes)."""
    final_like = rule["doc_class"] in ("FINAL_RULE", "FINAL_RULE_REQUEST_FOR_COMMENTS")
    order = ""
    if rule["publication_date"] and doc["publication_date"]:
        if rule["publication_date"] < doc["publication_date"]:
            order = "rule published BEFORE this dataset document; cannot be its outcome. "
    if doc["doc_class"] == "WITHDRAWAL" and final_like:
        return "CONFLICT_REVIEW", (order + "Dataset doc is a withdrawal but a final AD rule exists in the same docket; "
                                   "not resolved automatically.")
    if not final_like:
        return "CANDIDATE_SAME_DOCKET", order + f"Rule class {rule['doc_class']}; same docket only."
    if evidence and not order:
        return "VERIFIED_FINAL_RULE", "Docket match plus quoted back-reference to this document."
    if evidence and order:
        return "CANDIDATE_SAME_DOCKET", order + "Back-reference matched but date order is inconsistent."
    return "CANDIDATE_SAME_DOCKET", order + "Same docket; rule text has no back-reference to this specific document."


# ----------------------------------------------------------------- network
class Net:
    def __init__(self):
        self.calls = 0
        self.s = requests.Session()
        self.s.headers["User-Agent"] = config.HTTP_USER_AGENT

    def get(self, url, params=None, retries=4) -> requests.Response:
        assert url.startswith("https://www.federalregister.gov/"), url  # C5
        last = None
        for i in range(retries):
            time.sleep(config.HTTP_SLEEP_S)
            self.calls += 1
            try:
                r = self.s.get(url, params=params, timeout=60)
                if r.status_code == 404:
                    return r
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                last = e
                time.sleep(2 ** i)
        raise RuntimeError(f"failed {url}: {last}")


def _safe(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def search_docket(net: Net, docket: str) -> list[dict]:
    d = config.FR_FINAL_RULES_DIR / "search"
    d.mkdir(parents=True, exist_ok=True)
    results, page = [], 1
    while True:
        p = d / (f"{_safe(docket)}.json" if page == 1 else f"{_safe(docket)}_p{page}.json")
        if p.exists():
            data = json.loads(p.read_text())
        else:
            params = [("conditions[docket_id]", docket), ("conditions[type][]", "RULE"),
                      ("conditions[agencies][]", "federal-aviation-administration"),
                      ("per_page", 50), ("page", page), ("order", "oldest")]
            params += [("fields[]", f) for f in SEARCH_FIELDS]
            data = net.get(f"{config.FR_API}/documents.json", params).json()
            p.write_text(json.dumps(data, indent=1, sort_keys=True))
        results += data.get("results", [])
        if page >= data.get("total_pages", 1):
            return results
        page += 1


def fetch_xml(net: Net, rule: dict):
    """Returns (bytes|None, sha256|None); cached under FR_FINAL_RULES_DIR/{docnum}/."""
    d = config.FR_FINAL_RULES_DIR / rule["document_number"]
    x = d / "full_text.xml"
    if not x.exists():
        url = rule.get("full_text_xml_url")
        if not url:
            return None, None
        r = net.get(url)
        if r.status_code != 200 or not r.content.lstrip().startswith(b"<"):
            return None, None
        d.mkdir(parents=True, exist_ok=True)
        x.write_bytes(r.content)
        (d / "full_text.xml.sha256").write_text(hashlib.sha256(r.content).hexdigest() + "\n")
        (d / "metadata.json").write_text(json.dumps(rule, indent=1, sort_keys=True))
    b = x.read_bytes()
    return b, hashlib.sha256(b).hexdigest()


# ----------------------------------------------------------------- pipeline
def load_dataset_docs() -> list[dict]:
    docs, seen = [], set()
    with open(config.SOURCE_MANIFEST, newline="") as f:
        for row in csv.DictReader(f):
            n = row["docnum"].strip()
            p = config.FR_METADATA_DIR / f"{n}.json"
            if not n or n in seen or not p.exists():
                continue
            seen.add(n)
            m = json.loads(p.read_text())
            if "docket_ids" not in m:
                continue
            docs.append({"docnum": n, "dockets": normalize_dockets(m["docket_ids"]),
                         "citation": f"{m['citation'].split()[0]} FR {m['start_page']}" if m.get("citation") else None,
                         "publication_date": m.get("publication_date"),
                         "action": m.get("action"), "doc_class": doc_class(m.get("action"))})
    return sorted(docs, key=lambda d: d["docnum"])


def run() -> dict:
    net = Net()
    docs = load_dataset_docs()
    dockets = sorted({d for doc in docs for d in doc["dockets"]})
    rules, discarded = {}, []
    for dk in dockets:
        for hit in search_docket(net, dk):
            hd = normalize_dockets(hit.get("docket_ids"))
            if docket_key(dk) not in {docket_key(x) for x in hd}:
                discarded.append({"queried": dk, "docnum": hit["document_number"], "docket_ids": hit.get("docket_ids")})
                continue
            rules.setdefault(hit["document_number"], hit)
    out_rules, texts, links = [], {}, []
    for dn in sorted(rules):
        h = rules[dn]
        b, sha = fetch_xml(net, h)
        text = normalized_text(b) if b else ""
        texts[dn] = text
        ad, am = extract_ad_amendment(text) if text else (None, None)
        h["_dockets"] = normalize_dockets(h.get("docket_ids"))
        h["_class"] = classify_rule(h)
        out_rules.append({
            "fr_docnum": dn, "title": h.get("title"), "doc_class": h["_class"], "action_raw": h.get("action"),
            "publication_date": h.get("publication_date"), "effective_on": h.get("effective_on"),
            "citation": h.get("citation"), "docket_ids": h["_dockets"], "xml_url": h.get("full_text_xml_url"),
            "pdf_url": h.get("pdf_url"), "xml_sha256": sha, "ad_number": ad, "amendment": am,
            "supersedes": extract_supersedes(text) if text else [],
        })
    by_doc = {r["fr_docnum"]: r for r in out_rules}
    linked = set()
    for doc in docs:
        for dn in sorted(rules):
            sh = shared_dockets(doc["dockets"], rules[dn]["_dockets"])
            if not sh:
                continue
            rule = by_doc[dn]
            conf = []
            ev = find_backrefs(texts[dn], doc, conf) if texts[dn] else []
            status, notes = decide_status(doc, rule, ev)
            if conf:
                notes += " Rejected evidence: " + "; ".join(conf)
            if not texts[dn]:
                notes += " (rule full text unavailable)"
            links.append({"dataset_docnum": doc["docnum"], "rule_docnum": dn, "docket": "; ".join(sh),
                          "status": status, "evidence": ev if status in ("VERIFIED_FINAL_RULE", "CONFLICT_REVIEW") or ev else [],
                          "notes": notes})
            linked.add(doc["docnum"])
    links.sort(key=lambda l: (l["dataset_docnum"], l["rule_docnum"]))
    result = {"generated_from": {"manifest_sha256": hashlib.sha256(config.SOURCE_MANIFEST.read_bytes()).hexdigest(),
                                 "n_dataset_docs": len(docs)},
              "rules": out_rules, "links": links,
              "dataset_docs_without_rules": sorted(d["docnum"] for d in docs if d["docnum"] not in linked)}
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    (config.PROCESSED / "final_rule_links.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    config.FR_FINAL_RULES_DIR.mkdir(parents=True, exist_ok=True)
    (config.FR_FINAL_RULES_DIR / "discarded_hits.json").write_text(
        json.dumps(sorted(discarded, key=lambda d: (d["queried"], d["docnum"])), indent=1, sort_keys=True) + "\n")
    result["_stats"] = {"dockets": len(dockets), "network_calls": net.calls, "discarded": len(discarded)}
    result["_docs"] = docs
    return result
