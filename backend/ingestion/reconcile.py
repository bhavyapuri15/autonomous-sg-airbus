"""Reconciliation (A7): exact accounting 431 rows -> 428 rows with docnum -> 420 unique docs. Writes notes/reconciliation.md.
Every number in the output is computed here from the DB / manifest / metadata."""
import collections, datetime as dt, json, re, sqlite3
from pathlib import Path
from backend import config
from backend.ingestion import schema_normalizer as sn
from backend.ingestion.build_db import _tokens

OUT = config.ROOT / "notes" / "reconciliation.md"
DRS_RE = re.compile(r"FR-ADNPRM-((?:[A-Z]\d?-)?\d{4}-\d+)-")


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in r) + " |")
    return "\n".join(out)


SERIAL_RE = re.compile(r"serial\s+n|\bS/Ns?\b|\bserial\b", re.I)
AD_RE = re.compile(r"(?<![\d-])((?:19|20)?\d{2}-\d{2}-\d{2})(?![\d-])")


def _count_files(pattern_dir, names, docnums):
    return sum(1 for d in docnums if any((Path(pattern_dir) / d / n).exists() for n in names))


def index_sections(conn, recs, docs, by_doc):
    """Sections 0 (corpus counts) and 6-9 (organiser index checks). Returns (markdown lines, stats dict)."""
    from backend.ingestion import index_loader as il
    L, st = [], {}
    oi = [dict(r) for r in conn.execute("SELECT * FROM organiser_index ORDER BY record_id")]
    if not oi:
        return ["## 6. Organiser index", "", "No organiser_index table content (index workbook absent).", ""], st
    chains = [dict(r) for r in conn.execute("SELECT * FROM revision_chains ORDER BY docket_number, version")]
    rec_by_row = {r["row"]: r for r in recs}
    # ---- corpus counts ---------------------------------------------------------------------------------------------------
    dn_org = sorted(docs)
    xml_n = _count_files(config.FR_DOCS_DIR, ["full_text.xml"], dn_org)
    pdf_n = _count_files(config.FR_DOCS_DIR, ["document.pdf"], dn_org)
    parsed = sum(1 for d in docs.values() if d["extraction_status"] == "ok")
    pages_n = conn.execute("SELECT count(*) FROM pages WHERE fr_docnum IN (SELECT fr_docnum FROM documents WHERE source='organiser_sheet')").fetchone()[0]
    fr_docs = conn.execute("SELECT count(*) FROM documents WHERE source='fr_final_rule_lookup'").fetchone()[0]
    fr_pages = conn.execute("SELECT count(*) FROM pages WHERE fr_docnum IN (SELECT fr_docnum FROM documents WHERE source='fr_final_rule_lookup')").fetchone()[0]
    chunks_total = chunks_org = None
    if config.SEARCH_DB_PATH.exists():
        sc = sqlite3.connect(config.SEARCH_DB_PATH)
        chunks_total = sc.execute("SELECT count(*) FROM chunks").fetchone()[0]
        chunks_org = sc.execute("SELECT count(*) FROM chunks WHERE source='organiser_sheet'").fetchone()[0]
        sc.close()
    fail_p = config.PROCESSED / "ingest_failures.json"
    dl_fail = len(json.loads(fail_p.read_text()).get("download_failures", [])) if fail_p.exists() else None
    meta_only = sum(1 for r in recs if not r["fr_docnum"])
    st["corpus"] = dict(organiser_records=len(oi), unique_dockets=len({r["docket_number"] for r in oi}), unique_fr_docs=len(docs), xml=xml_n, pdf=pdf_n,
                        parsed=parsed, pages=pages_n, chunks_total=chunks_total, chunks_organiser=chunks_org, failed_downloads=dl_fail,
                        metadata_only=meta_only, final_rule_docs=fr_docs, final_rule_pages=fr_pages)
    L += ["## 0. Corpus counts (index-aligned)", "",
          _md_table(["quantity", "count"], [
              ["organiser records (organiser_index)", len(oi)],
              ["unique dockets (index docket_number)", st["corpus"]["unique_dockets"]],
              ["unique FR documents (organiser_sheet documents)", len(docs)],
              ["downloaded XML files (organiser docs)", xml_n],
              ["downloaded PDFs (organiser docs)", pdf_n],
              ["parsed documents (extraction_status ok)", parsed],
              ["indexed pages (organiser docs, pages table)", pages_n],
              ["indexed chunks, organiser docs (search.sqlite)", chunks_org],
              ["indexed chunks, all (organiser + final-rule enrichment; search.sqlite)", chunks_total],
              ["failed downloads (ingest_failures.json)", dl_fail],
              ["metadata-only records (no FR document)", meta_only],
              ["enrichment: final-rule documents / pages (source fr_final_rule_lookup)", f"{fr_docs} / {fr_pages}"]]), ""]
    # ---- 6. mapping and discrepancies ------------------------------------------------------------------------------------
    meth = collections.Counter(r["match_method"] for r in oi)
    ids = [r["record_id"] for r in oi]
    rows_mapped = [r["sheet_row"] for r in oi]
    st["mapping"] = dict(methods=dict(meth), unique_ids=len(set(ids)), unique_rows=len(set(rows_mapped)))
    L += ["## 6. Index vs original workbook: record_id mapping", "",
          "Hypothesis NPRM-001 = sheet row 2, in order, is verified per row: a row is `positional_verified` only if docket, ISO publish date, pages and subject all "
          "equal the original row; otherwise a unique content match is searched (`content_unique`); anything else is reported. Nothing is assumed.", "",
          _md_table(["match_method", "records"], sorted(meth.items())), "",
          f"Unique record_ids: {len(set(ids))}; unique original sheet rows mapped: {len(set(rows_mapped))}; "
          f"`records.record_id` populated for {sum(1 for r in recs if r['record_id'])} rows.", ""]
    dcount = collections.Counter()
    pd_diff = []
    for r in oi:
        disc = json.loads(r["discrepancies_json"])
        for k in disc: dcount[k] += 1
        if "publish_date" in disc: pd_diff.append((r["record_id"], r["sheet_row"], disc["publish_date"]))
    st["discrepancy_counts"] = dict(dcount)
    L += ["Per-field discrepancies (index vs original sheet, from `organiser_index.discrepancies_json`):", "",
          _md_table(["field", "records"], sorted(dcount.items()) or [["(none)", 0]]), "",
          "`federal_register_link_compound` = the index cell holds several URLs (typically the NPRM link followed by `Withdrawal:` and another URL) or trailing text; "
          "it is stored verbatim, and the link docnums are listed in the discrepancy. `federal_register_link_not_a_url` = the cell holds pasted document text instead of a URL "
          "(so the '406 filled links' include rows that carry no usable link).", ""]
    L += [f"Publish-date differences (index ISO vs our parsed `records.publish_date`): {len(pd_diff)}. " +
          ("" if not pd_diff else "Examples: " + "; ".join(f"{a} row {b} {c}" for a, b, c in pd_diff[:8])), "",
          "Index ISO publish dates are canonical for organiser records (`organiser_index.publish_date`); `records.publish_date` is left as parsed.", ""]
    # ---- 7. FR link comparison -------------------------------------------------------------------------------------------
    agree_first, agree_later, disagree, ours_only, idx_only, neither = [], [], [], [], [], 0
    nlink = pasted = 0
    for r in oi:
        dns = il.link_docnums(r["federal_register_link"])
        ours = r["fr_docnum"]
        if r["federal_register_link"]:
            nlink += 1
        if dns and ours:
            if dns[0] == ours: agree_first.append(r["record_id"])
            elif ours in dns: agree_later.append((r["record_id"], ours, dns))
            else: disagree.append((r["record_id"], ours, dns))
        elif ours and not dns:
            ours_only.append(r["record_id"])
            if r["federal_register_link"]: pasted += 1
        elif dns and not ours:
            idx_only.append((r["record_id"], dns))
        else:
            neither += 1
    st["fr_links"] = dict(index_links=nlink, ours=sum(1 for r in oi if r["fr_docnum"]), agree_first_url=len(agree_first), agree_non_first_url=len(agree_later),
                          disagree=len(disagree), ours_only=len(ours_only), ours_only_cell_is_pasted_text=pasted, index_only=len(idx_only), neither=neither)
    L += ["## 7. Index `federal_register_link` vs our resolved FR docnums", "",
          _md_table(["comparison", "records"], [
              ["index has a link", nlink], ["we resolved a docnum", st["fr_links"]["ours"]],
              ["agree (our docnum == first URL docnum)", len(agree_first)],
              ["agree only via a later URL in a compound cell", len(agree_later)],
              ["disagree (our docnum not in any index URL)", len(disagree)],
              ["we resolved a docnum but the index has no parseable FR URL", len(ours_only)],
              ["  of which the index cell is non-empty pasted document text (no URL)", pasted],
              ["  of which the index cell is empty", len(ours_only) - pasted],
              ["index cells holding a parseable FR URL", sum(1 for r in oi if il.link_docnums(r["federal_register_link"]))],
              ["index has a link but we have no docnum", len(idx_only)],
              ["neither", neither]]), ""]
    if agree_later or disagree or idx_only:
        L += [_md_table(["record_id", "kind", "our docnum", "index link docnums"],
                        [[a, "later_url", b, ",".join(c)] for a, b, c in agree_later] + [[a, "DISAGREE", b, ",".join(c)] for a, b, c in disagree] +
                        [[a, "index_only", "", ",".join(c)] for a, c in idx_only]), ""]
    if ours_only:
        L += ["Records with our docnum but no index URL (cell empty or pasted text): " + ", ".join(ours_only[:12]) + (" ..." if len(ours_only) > 12 else ""), ""]
    # ---- 8. revision chains ----------------------------------------------------------------------------------------------
    by_dk = collections.defaultdict(list)
    for c in chains: by_dk[c["docket_number"]].append(c)
    orig_by_docket = collections.defaultdict(set)
    for r in recs:
        if r["record_id"]: orig_by_docket[r["docket_raw"]].add(r["record_id"])
    oi_by_id = {r["record_id"]: r for r in oi}
    multi_orig = {k: v for k, v in orig_by_docket.items() if len(v) > 1}
    not_multi = [k for k, v in by_dk.items() if len(v) < 2]
    bad_latest = [k for k, v in by_dk.items() if sum(1 for c in v if c["status"] == "latest") != 1]
    ties, missing, latest_ne_max, latest_not_last, set_mismatch, field_mismatch, total_mismatch = [], [], [], [], [], [], []
    for k, v in sorted(by_dk.items()):
        dates = [c["publish_date"] for c in v]
        if any(not d or not il.valid_iso(d) for d in dates): missing.append(k)
        valid = [d for d in dates if d and il.valid_iso(d)]
        cnt = collections.Counter(valid)
        for d, n in cnt.items():
            if n > 1: ties.append((k, d, [c["record_id"] for c in v if c["publish_date"] == d], [c["status"] for c in v if c["publish_date"] == d]))
        lat = [c for c in v if c["status"] == "latest"]
        if lat and valid and lat[0]["publish_date"] != max(valid): latest_ne_max.append(k)
        if lat and lat[0]["version"] != max(c["version"] for c in v): latest_not_last.append(k)
        if {c["record_id"] for c in v} != orig_by_docket.get(k, set()): set_mismatch.append(k)
        if any(c["versions_total"] != len(v) for c in v): total_mismatch.append(k)
        for c in v:
            o = oi_by_id.get(c["record_id"])
            if not o or o["docket_number"] != k or o["publish_date"] != c["publish_date"] or sn.norm_ws(o["subject"]) != sn.norm_ws(c["subject"]):
                field_mismatch.append(c["record_id"])
    st["chains"] = dict(dockets=len(by_dk), rows=len(chains), expected_dockets_in_sheet=len(multi_orig), not_multi=len(not_multi), bad_latest=len(bad_latest),
                        ties=len(ties), missing_dates=len(missing), latest_ne_max=len(latest_ne_max), latest_not_last_version=len(latest_not_last),
                        record_set_mismatch=len(set_mismatch), versions_total_mismatch=len(total_mismatch), row_field_mismatch=len(field_mismatch))
    L += ["## 8. revision_chains checks", "",
          _md_table(["check", "result"], [
              ["dockets in revision_chains", f"{len(by_dk)} (chain rows {len(chains)})"],
              ["dockets with more than 1 record in the original sheet", len(multi_orig)],
              ["chain dockets with fewer than 2 records", len(not_multi)],
              ["dockets without exactly one `latest`", len(bad_latest)],
              ["ties on publish_date inside a docket", len(ties)],
              ["dockets with a missing/non-ISO date", len(missing)],
              ["`latest` date != max publish_date", len(latest_ne_max)],
              ["`latest` is not the highest version number", len(latest_not_last)],
              ["versions_total != rows in chain", len(total_mismatch)],
              ["chain record set != original-sheet rows sharing the docket", len(set_mismatch)],
              ["chain row docket/date/subject != organiser_index row", len(field_mismatch)]]), ""]
    if ties:
        L += ["Ties on publish_date (same-day versions; `latest` is therefore decided by the organiser's version order, not by date alone):", "",
              _md_table(["docket", "date", "record_ids", "statuses"], [[a, b, ",".join(c), ",".join(d)] for a, b, c, d in ties]), ""]
    for name, lst in (("missing/non-ISO dates", missing), ("latest != max date", latest_ne_max), ("record-set mismatches", set_mismatch)):
        if lst: L += [f"Dockets with {name}: " + ", ".join(lst), ""]
    # ---- 9. supersedes_ad vs text-derived edges ---------------------------------------------------------------------------
    edges = collections.defaultdict(set)
    for r in conn.execute("SELECT src, dst FROM relations WHERE type='PROPOSES_TO_SUPERSEDE'"):
        edges[r[0]].add(r[1].replace("AD:", "").strip())
    def canon(a):
        return re.sub(r"^(\d{2})-", lambda m: ("19" if int(m.group(1)) >= 40 else "20") + m.group(1) + "-", a)
    both = idx_only_s = txt_only = 0
    ex_both, ex_idx, ex_txt = [], [], []
    idx_n = 0
    for r in oi:
        iv = {canon(a) for a in AD_RE.findall(r["supersedes_ad"] or "")}
        tv = {canon(a) for a in edges.get(r["fr_docnum"], set())} if r["fr_docnum"] else set()
        if iv: idx_n += 1
        if iv and tv and iv & tv:
            both += 1; ex_both.append(f"{r['record_id']}: {sorted(iv)}")
        elif iv and tv:
            idx_only_s += 1; ex_idx.append(f"{r['record_id']}: index {sorted(iv)} vs text {sorted(tv)}")
        elif iv:
            idx_only_s += 1; ex_idx.append(f"{r['record_id']}: index {sorted(iv)} vs text none")
        elif tv:
            txt_only += 1; ex_txt.append(f"{r['record_id']}: text {sorted(tv)}")
    st["supersedes"] = dict(index_filled=idx_n, agree=both, index_only=idx_only_s, text_only=txt_only, text_edges_total=sum(len(v) for v in edges.values()))
    L += ["## 9. `supersedes_ad` (index) vs text-derived PROPOSES_TO_SUPERSEDE edges", "",
          "Compared per record on the set of AD numbers (two-digit years canonicalised). The index field is a proposed supersession only and is never treated as operative.", "",
          _md_table(["comparison", "records"], [
              ["records with index supersedes_ad", idx_n],
              ["agree (sets intersect)", both],
              ["index-only (index has it, our text edges do not agree)", idx_only_s],
              ["text-only (we have a PROPOSES_TO_SUPERSEDE edge, index empty)", txt_only]]), "",
          "Examples agree: " + "; ".join(ex_both[:4]), "", "Examples index-only: " + "; ".join(ex_idx[:6]), "", "Examples text-only: " + "; ".join(ex_txt[:6]), ""]
    # ---- 10. serial flag --------------------------------------------------------------------------------------------------
    flagged = [r for r in oi if r["mentions_serial_numbers"]]
    app_ser = {}
    for dn, txt in conn.execute("SELECT fr_docnum, text FROM sections WHERE kind='proposed_ad_paragraph' AND level=1 AND heading LIKE 'Applicab%'"):
        if SERIAL_RE.search(txt or ""): app_ser[dn] = True
    sum_ser = {r["record_id"] for r in oi if SERIAL_RE.search(r["summary"] or "")}
    fl_app = [r["record_id"] for r in flagged if r["fr_docnum"] in app_ser]
    fl_noapp = [r["record_id"] for r in flagged if r["fr_docnum"] not in app_ser]
    app_noflag = [r["record_id"] for r in oi if not r["mentions_serial_numbers"] and r["fr_docnum"] in app_ser]
    st["serial"] = dict(flagged=len(flagged), flagged_with_serial_in_applicability_text=len(fl_app), flagged_without=len(fl_noapp),
                        unflagged_with_serial_in_applicability_text=len(app_noflag), flagged_summary_mentions=sum(1 for r in flagged if r["record_id"] in sum_ser))
    L += ["## 10. `mentions_serial_numbers` flag vs our applicability data", "",
          "Our data = the FR full-text Applicability paragraph (section parse) containing 'serial number' / S/N. The flag is a summary-level hint only, never evidence.", "",
          _md_table(["comparison", "records"], [
              ["flag = yes", len(flagged)],
              ["flag = yes and our Applicability text mentions serial numbers", len(fl_app)],
              ["flag = yes but our Applicability text has no serial reference", len(fl_noapp)],
              ["flag = no but our Applicability text mentions serial numbers", len(app_noflag)],
              ["flag = yes and the index summary itself mentions serial numbers", st["serial"]["flagged_summary_mentions"]]]), "",
          "Flagged without serial text in our Applicability paragraph: " + (", ".join(fl_noapp) or "none"), ""]
    return L, st


def reconcile(db_path=None, out_path=OUT):
    conn = sqlite3.connect(db_path or config.DB_PATH); conn.row_factory = sqlite3.Row
    recs = [dict(r) for r in conn.execute("SELECT * FROM records ORDER BY row")]
    docs = {r["fr_docnum"]: dict(r) for r in conn.execute("SELECT * FROM documents WHERE source='organiser_sheet'")}
    L = []
    n_rows = len(recs)
    with_doc = [r for r in recs if r["fr_docnum"]]
    unresolved = [r for r in recs if not r["fr_docnum"]]
    uniq = {r["fr_docnum"] for r in with_doc}
    L += ["# Reconciliation (amendment A7)", "",
          "Generated by `backend/ingestion/reconcile.py` from `data/indexes/ad.sqlite`; every number below is computed, none typed by hand.", "",
          "## 1. Funnel", "",
          _md_table(["step", "count"], [
              ["sheet rows (records)", n_rows],
              ["rows with an FR docnum", len(with_doc)],
              ["rows without an FR docnum (metadata-only)", len(unresolved)],
              ["unique FR documents (documents table)", len(docs)],
              ["unique docnums referenced by records", len(uniq)],
              ["rows beyond the first per docnum (duplicates)", len(with_doc) - len(uniq)]]), "",
          f"Check: {n_rows} - {len(unresolved)} = {len(with_doc)}; {len(with_doc)} - {len(with_doc) - len(uniq)} = {len(uniq)}; documents table has {len(docs)}.", "",
          "Match confidence of the rows with a docnum:", "",
          _md_table(["match_confidence", "docnum_source", "rows"],
                    [[k[0], k[1], v] for k, v in sorted(collections.Counter((r["match_confidence"], r["docnum_source"] or "") for r in recs).items())]), ""]
    ver = collections.Counter(r["match_verified"] for r in recs if r["match_confidence"] == "inferred_search")
    L += [f"Inferred (search) rows: {sum(ver.values())}; match_verified true={ver.get(1, 0)}, false={ver.get(0, 0)} "
          "(checks: title token Jaccard >= 0.5, sheet page range == FR range, sheet publish date or citation-text date == FR publication_date).", ""]
    # shared docnums
    by_doc = collections.defaultdict(list)
    for r in with_doc: by_doc[r["fr_docnum"]].append(r)
    shared = {d: rs for d, rs in by_doc.items() if len(rs) > 1}
    L += [f"## 2. FR docnums shared by multiple rows ({len(shared)} docnums, {sum(len(v) for v in shared.values())} rows)", ""]
    rows = []
    for d, rs in sorted(shared.items()):
        same_docket = len({r["docket_norm"] for r in rs}) == 1
        same_pages = len({r["page_number_raw"] for r in rs}) == 1
        same_pub = len({r["publish_date"] for r in rs}) == 1
        same_subj = len({sn.norm_ws(r["subject"]) for r in rs}) == 1
        drs = [DRS_RE.search(r["drs_url"] or "") for r in rs]
        drs_ids = ",".join(m.group(1) if m else "opaque" for m in drs)
        if same_docket and same_pages and same_pub:
            why = "same document listed twice (identical docket, pages, publish date)"
        elif same_docket:
            why = "same docket, different sheet pages/dates -> sheet rows disagree about one FR doc"
        else:
            why = "different dockets resolve to one FR doc (e.g. one FR notice covers several dockets, or a wrong link)"
        rows.append([d, ",".join(str(r["row"]) for r in rs), "; ".join(r["docket_norm"] for r in rs),
                     "; ".join(r["match_confidence"] for r in rs), docs[d]["docket_ids_json"], "; ".join(r["page_number_raw"] for r in rs),
                     "; ".join(str(r["publish_date"]) for r in rs), f"same_subject={same_subj}", drs_ids, why])
    L += [_md_table(["docnum", "rows", "sheet dockets", "match", "FR docket_ids", "sheet pages", "sheet publish", "subject", "DRS ids in col A", "assessment"], rows), ""]
    # unresolved
    L += [f"## 3. Unresolved rows ({len(unresolved)})", "",
          _md_table(["row", "docket", "subject", "publish", "pages", "col R kind", "drs_url tail"],
                    [[r["row"], r["docket_raw"], sn.norm_ws(r["subject"])[:110], r["publish_date"], r["page_number_raw"], r["col_r_kind"], (r["drs_url"] or "")[-40:]] for r in unresolved]), "",
          "These rows stay in `records` as metadata-only (no FR document; col R is pasted text or empty).", ""]
    # duplicate dockets
    bd = collections.defaultdict(list)
    for r in recs: bd[r["docket_norm"]].append(r)
    dups = {k: v for k, v in bd.items() if len(v) > 1}
    comp = collections.defaultdict(list)
    for k, v in dups.items():
        key = "+".join(sorted((docs[r["fr_docnum"]]["doc_class"] if r["fr_docnum"] else "UNRESOLVED") for r in v))
        comp[key].append(k)
    L += [f"## 4. Duplicate dockets ({len(dups)} dockets, {sum(len(v) for v in dups.values())} rows), grouped by doc_class composition", "",
          _md_table(["composition", "dockets", "example dockets"], [[k, len(v), ", ".join(sorted(v)[:4])] for k, v in sorted(comp.items(), key=lambda kv: (-len(kv[1]), kv[0]))]), "",
          "Sharing a docket never implies succession (A5); this is only a count.", ""]
    # mismatches
    mm = [r for r in recs if r["fr_docnum"] and ("sheet_fr_date_mismatch" in r["dq_flags_json"] or "sheet_fr_pages_mismatch" in r["dq_flags_json"])]
    dm = [r for r in mm if "sheet_fr_date_mismatch" in r["dq_flags_json"]]
    pm = [r for r in mm if "sheet_fr_pages_mismatch" in r["dq_flags_json"]]
    L += [f"## 5. Sheet-vs-FR mismatches: {len(dm)} date, {len(pm)} pages ({len(mm)} distinct rows)", "",
          "Evidence only. `drs_docnum` = docnum embedded in the col-A DRS link; `url_docnum` = docnum used for the match; "
          "`cite_date==FR` = date written in the sheet Citation text equals FR publication_date; `sheet_consistent` = Citation-text date equals "
          "the row's publish date or is +1 day (the known legacy offset); `other_row_matches` = another row with the same docnum agrees with FR on date and pages. "
          "Verdict rules, in order: (1) `fr_link_suspect` if the FR doc's docket_ids lack the sheet docket, or title Jaccard < 0.5, or drs_docnum != url_docnum; "
          "(2) `fr_link_suspect(stale col R link)` if sheet_consistent and other_row_matches and not cite_date==FR (the row's own date, pages and citation agree with each other, "
          "a sibling row matches the FR doc, so this row probably describes a later publication of the same docket); "
          "(3) `sheet_pages_suspect` if cite_date==FR but pages differ; (4) otherwise `undetermined`.", ""]
    rows = []
    verdicts = collections.Counter()
    for r in mm:
        d = docs[r["fr_docnum"]]
        m = DRS_RE.search(r["drs_url"] or ""); drs = m.group(1) if m else None
        dock_ok = any(r["docket_norm"] in x for x in json.loads(d["docket_ids_json"]))
        jac = round(len(_tokens(r["subject"]) & _tokens(d["title"])) / max(1, len(_tokens(r["subject"]) | _tokens(d["title"]))), 2)
        sp = sn.parse_pages(r["page_number_raw"])
        cd = sn.citation_date(r["citation"])
        cite_eq = cd == d["publication_date"]
        consistent = cd is not None and r["publish_date"] is not None and cd in (r["publish_date"], (dt.date.fromisoformat(r["publish_date"]) + dt.timedelta(days=1)).isoformat())
        others = [o for o in by_doc[r["fr_docnum"]] if o["row"] != r["row"]]
        other_ok = any(o["publish_date"] == d["publication_date"] or sn.citation_date(o["citation"]) == d["publication_date"] for o in others) and \
            any(sn.parse_pages(o["page_number_raw"]) == (d["start_page"], d["end_page"]) for o in others)
        ev = [f"docket_in_FR={dock_ok}", f"title_jaccard={jac}", f"drs_docnum={drs or 'opaque'}", f"url_docnum={r['fr_docnum']}",
              f"cite_date==FR:{cite_eq}", f"sheet_consistent={consistent}", f"other_row_matches={other_ok}"]
        if (not dock_ok) or jac < 0.5 or (drs is not None and drs != r["fr_docnum"]):
            verdict = "fr_link_suspect"
        elif consistent and other_ok and not cite_eq:
            verdict = "fr_link_suspect(stale col R link)"
        elif cite_eq:
            verdict = "sheet_pages_suspect"
        else:
            verdict = "undetermined"
        verdicts[verdict] += 1
        rows.append([r["row"], r["docket_norm"], r["match_confidence"], f"{r['publish_date']} / {sp}", f"{d['publication_date']} / ({d['start_page']}, {d['end_page']})",
                     "date" if r in dm else "", "pages" if r in pm else "", "; ".join(ev), verdict])
    L += [_md_table(["row", "docket", "match", "sheet publish / pages", "FR date / pages", "date mm", "pages mm", "evidence", "verdict"], rows), "",
          "Verdict counts: " + ", ".join(f"{k}={v}" for k, v in sorted(verdicts.items())) + ".", "",
          "These are evidence-based assessments, not corrections: no sheet value or FR link is modified; the rows keep the flags "
          "`sheet_fr_date_mismatch` / `sheet_fr_pages_mismatch` in `records.dq_flags_json`.", ""]
    extra, ex_stats = index_sections(conn, recs, docs, by_doc)
    L += extra
    Path(out_path).write_text("\n".join(L) + "\n")
    conn.close()
    return dict(index=ex_stats, rows=n_rows, with_doc=len(with_doc), unique=len(uniq), unresolved=len(unresolved), shared=len(shared),
                dup_dockets=len(dups), date_mm=len(dm), page_mm=len(pm), verdicts=dict(verdicts))
