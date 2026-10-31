"""Organiser index workbook (challenge4_ad_index.xlsx): untrusted data, read with openpyxl only (no formulas evaluated,
nothing executed). Header rows are located by content, never by fixed row number. Raw cell strings are kept as given."""
import datetime as dt, hashlib, json, re
import openpyxl
from backend import config
from backend.ingestion import schema_normalizer as sn

NPRM_COLS = ["record_id", "docket_number", "subject", "issue_date", "publish_date", "make", "model", "product_type", "product_subtype",
             "ad_number", "supersedes_ad", "mentions_serial_numbers", "citation", "pages", "federal_register_link", "summary"]
CHAIN_COLS = ["docket_number", "version", "versions_total", "status", "record_id", "publish_date", "subject"]
RID_RE = re.compile(r"^NPRM-(\d{3,})$")
FR_LINK_DOCNUM = re.compile(r"federalregister\.gov/(?:documents/\d{4}/\d{2}/\d{2}/|[a-z]/)([A-Za-z]\d{0,2}-\d{4}-\d{4,6}|[A-Za-z]\d{1,2}-\d{3,5}|\d{2,4}-\d{3,6})(?![\w-])")


def verify_sha():
    h = hashlib.sha256(config.INDEX_XLSX.read_bytes()).hexdigest()
    if h != config.INDEX_SHA256:
        raise RuntimeError(f"challenge4_ad_index.xlsx sha256 mismatch: {h}")
    return h


def _s(v):
    return None if v is None else str(v)


def _table(ws, first_header):
    """Rows after the header row (the row whose first cell == first_header). Returns [(sheet_row, {col: value})]."""
    header_at = None
    for r in range(1, min(ws.max_row, 20) + 1):
        if ws.cell(r, 1).value == first_header:
            header_at = r
            break
    if header_at is None:
        raise RuntimeError(f"header row starting with {first_header!r} not found in sheet {ws.title!r}")
    names = [ws.cell(header_at, c).value for c in range(1, ws.max_column + 1)]
    out = []
    for r in range(header_at + 1, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, len(names) + 1)]
        if vals[0] is None or str(vals[0]).strip() == "":
            continue
        out.append((r, {n: _s(v) for n, v in zip(names, vals)}))
    return names, out


def load_index():
    """Returns dict(records=[...], chains=[...], notes=[...]). Records keep sheet_row (row in the index workbook)."""
    verify_sha()
    wb = openpyxl.load_workbook(config.INDEX_XLSX, read_only=False, data_only=True)
    names, rows = _table(wb["nprm_index"], "record_id")
    if names[:len(NPRM_COLS)] != NPRM_COLS:
        raise RuntimeError(f"unexpected nprm_index header: {names}")
    records = []
    for r, d in rows:
        d["index_sheet_row"] = r
        records.append(d)
    cnames, crows = _table(wb["revision_chains"], "docket_number")
    if cnames[:len(CHAIN_COLS)] != CHAIN_COLS:
        raise RuntimeError(f"unexpected revision_chains header: {cnames}")
    chains = [dict(d, index_sheet_row=r) for r, d in crows]
    notes = [tuple(x) for x in wb["data_notes"].iter_rows(min_row=2, values_only=True) if x[0]]
    return dict(records=records, chains=chains, notes=notes)


def rid_number(rid):
    m = RID_RE.match((rid or "").strip())
    return int(m.group(1)) if m else None


def link_docnums(link):
    return FR_LINK_DOCNUM.findall(link or "")


def link_is_clean(link):
    """A single plain URL (long documents/ form or short /a/ /d/ form) and nothing else."""
    if not link or re.search(r"\s|,|\\", link):
        return False
    return len(link_docnums(link)) == 1 and link.count("http") == 1


def valid_iso(s):
    try:
        return s is not None and dt.date.fromisoformat(s).isoformat() == s
    except ValueError:
        return False


def _eq(a, b):
    return sn.norm_ws(a or "") == sn.norm_ws(b or "")


def map_records(index_records, sheet_recs):
    """Verified record_id -> original sheet row mapping.
    For each index record the candidate set is every original row agreeing on docket, publish date (ISO), pages and subject.
    Method 'positional_verified' = the hypothesised row (record n = sheet row n+1) is in the candidate set;
    'content_unique' = positional row fails but exactly one other unclaimed row agrees; otherwise 'positional_unverified'
    (kept at the positional row, with the failing fields in discrepancies) or 'unmatched'. Never assumed.
    Returns [(index_record, sheet_rec|None, method, discrepancies dict)] in index order."""
    by_row = {r["row"]: r for r in sheet_recs}

    def checks(x, r):
        return dict(
            docket=(x["docket_number"] or "") == (r["docket_raw"] or ""),
            publish_date=(x["publish_date"] or "") == (r["publish_date"] or ""),
            pages=_eq(x["pages"], r["page_number_raw"]) or sn.parse_pages(x["pages"]) == sn.parse_pages(r["page_number_raw"]),
            subject=_eq(x["subject"], r["subject"]))

    def strict(x, r):
        return all(checks(x, r).values())

    out, claimed = [], set()
    for x in index_records:
        n = rid_number(x["record_id"])
        pos = by_row.get(n + 1) if n else None
        method, row = None, None
        if pos is not None and strict(x, pos):
            method, row = "positional_verified", pos
        else:
            cands = [r for r in sheet_recs if strict(x, r)]
            if len(cands) == 1:
                method, row = "content_unique", cands[0]
            elif pos is not None:
                method, row = "positional_unverified", pos
            else:
                method = "unmatched"
        out.append([x, row, method, {}])
        if row is not None and method != "positional_unverified":
            claimed.add(row["row"])
    # 1:1 enforcement: a row claimed twice is an error, not silently accepted
    seen = {}
    for x, row, method, _ in out:
        if row is not None:
            if row["row"] in seen:
                raise RuntimeError(f"sheet row {row['row']} mapped by both {seen[row['row']]} and {x['record_id']}")
            seen[row["row"]] = x["record_id"]
    for item in out:
        x, row, method, disc = item
        if row is None:
            continue
        c = checks(x, row)
        for k, ok in c.items():
            if not ok:
                disc[k] = "mismatch"
        # informational field comparisons (index value vs original sheet value)
        if x["issue_date"] != row["issue_date"]:
            disc["issue_date"] = dict(index=x["issue_date"], sheet=row["issue_date"])
        if not _eq(x["citation"], row["citation"]):
            disc["citation"] = dict(index=x["citation"], sheet=row["citation"])
        if (x["ad_number"] or "") != (row["ad_number"] or ""):
            disc["ad_number"] = dict(index=x["ad_number"], sheet=row["ad_number"])
        if (x["make"] or "") != (row["make_raw"] or ""):
            disc["make"] = dict(index=x["make"], sheet=row["make_raw"])
        if (x["publish_date"] or "") != (row["publish_date"] or ""):
            disc["publish_date"] = dict(index=x["publish_date"], sheet_parsed=row["publish_date"])
        if not valid_iso(x["publish_date"]):
            disc["publish_date_not_iso"] = x["publish_date"]
        elif not x["issue_date"] or not valid_iso(x["issue_date"]):
            disc["issue_date_not_iso"] = x["issue_date"]
        if x["federal_register_link"] and not link_docnums(x["federal_register_link"]):
            disc["federal_register_link_not_a_url"] = True   # cell holds pasted document text, no FR URL
        elif x["federal_register_link"] and not link_is_clean(x["federal_register_link"]):
            disc["federal_register_link_compound"] = link_docnums(x["federal_register_link"])  # several URLs / trailing text in one cell
        item[3] = disc
    return [tuple(i) for i in out]


def to_row(x, sheet_rec, method, disc, docnum_by_row):
    dn = docnum_by_row.get(sheet_rec["row"]) if sheet_rec else None
    return (x["record_id"], sheet_rec["row"] if sheet_rec else None, x["docket_number"], x["subject"], x["issue_date"], x["publish_date"],
            x["make"], x["model"], x["product_type"], x["product_subtype"], x["ad_number"], x["supersedes_ad"],
            1 if (x["mentions_serial_numbers"] or "").strip().lower() == "yes" else 0, x["citation"], x["pages"],
            x["federal_register_link"], x["summary"], dn, method, json.dumps(disc, sort_keys=True))
