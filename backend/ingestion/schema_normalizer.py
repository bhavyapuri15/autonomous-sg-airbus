"""Canonical record from raw sheet row. Raw values are kept verbatim elsewhere; this adds normalized columns."""
import datetime as dt, re

# Conservative make aliases: ONLY clear spelling/legal-suffix equivalents of the same named company.
# Deliberately NOT merged: Airbus vs Airbus Helicopters vs Airbus Canada vs Airbus Industrie vs Airbus Defence,
# Eurocopter*, Bell Helicopter Textron vs Bell Textron, Rolls-Royce plc/Corporation/Deutschland, Pratt & Whitney variants,
# Boeing vs McDonnell Douglas, Cessna vs Textron Aviation, GE variants.
MAKE_ALIASES = {
    "The Boeing Company": "Boeing",
    "Airbus SAS": "Airbus",
    "Bombardier Inc.": "Bombardier", "Bombardier, Inc.": "Bombardier",
    "CFM International S.A.": "CFM International", "CFM International, S.A.": "CFM International",
    "Embraer S.A.": "Embraer",
    "Gulfstream Aerospace Corporation": "Gulfstream Aerospace", "Gulfstream Aerospace LP": "Gulfstream Aerospace",
    "Leonardo S.p.A.": "Leonardo", "Leonardo S.p.a.": "Leonardo",
    "Piper Aircraft Inc.": "Piper", "Piper Aircraft, Inc.": "Piper", "Piper Aircraft Inc": "Piper",
    "Cessna Aircraft Company": "Cessna",
    "MD Helicopters, Inc.": "MD Helicopters", "MD Helicopters LLC": "MD Helicopters", "MD Helicopters Inc.": "MD Helicopters",
    "Mitsubishi Heavy Industries, Ltd.": "Mitsubishi Heavy Industries",
    "Scotts-Bell 47 Inc.": "Scotts-Bell 47 Inc",
    "Airbus Helicopters Deutschland GmbH (AHD)": "Airbus Helicopters Deutschland GmbH",
}


def norm_ws(s):
    return re.sub(r"\s+", " ", (s or "").replace("\\n", " ")).strip()


def iso_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def norm_docket(s):
    m = re.search(r"FAA-\d{4}-\d+", s or "")
    return m.group(0) if m else norm_ws(s)


def split_pipe(s):
    return [t.strip() for t in (s or "").split("|") if t.strip()]


def norm_make(s):
    return " | ".join(MAKE_ALIASES.get(t, t) for t in split_pipe(s))


FR_URL = re.compile(r"^(?:Withdrawal:\s*)?https?://(?:www\.)?federalregister\.gov/documents/\S+$", re.I)
SHORT = re.compile(r"^(?:Withdrawal:\s*)?https?://(?:www\.)?federalregister\.gov/[da]/\S+$", re.I)
ANY_URL = re.compile(r"^(?:Withdrawal:\s*)?https?://\S+$", re.I)


def col_r_kind(s):
    t = (s or "").strip()
    if not t:
        return "empty"
    if FR_URL.match(t):
        return "fr_url"
    if SHORT.match(t):
        return "short_url"
    if ANY_URL.match(t):
        return "other_url"
    return "embedded_text"


def parse_pages(s):
    m = re.search(r"(\d+)\s*(?:-\s*(\d+))?", s or "")
    if not m:
        return None
    a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
    return a, b


def normalize(raw):
    flags = []
    pub, iss, due = iso_date(raw["publish_date"]), iso_date(raw["issue_date"]), iso_date(raw["comments_due"])
    if raw["comments_due"].strip() and not due: flags.append("comments_due_unparsed")
    if not raw["comments_due"].strip(): flags.append("comments_due_empty")
    if due and pub and due <= pub: flags.append("comments_due_not_after_publish")
    if not raw["make"].strip(): flags.append("make_empty")
    if not raw["summary"].strip(): flags.append("summary_empty")
    if not raw["col_r"].strip(): flags.append("col_r_empty")
    if "\\n" in raw["summary"]: flags.append("summary_literal_backslash_n")
    cdate = citation_date(raw["citation"])
    if cdate and pub and cdate != pub: flags.append("publish_date_differs_from_citation_text_date")
    models = split_pipe(raw["model"])
    return dict(
        row=raw["row"], docket_raw=raw["docket"], docket_norm=norm_docket(raw["docket"]),
        subject=raw["subject"], status_raw=raw["status"], issue_date=iss, publish_date=pub, comments_due_date=due,
        make_raw=raw["make"], make_norm=norm_make(raw["make"]), models_raw=raw["model"], models=models,
        product_type=raw["product_type"], product_subtype=raw["product_subtype"], ad_number=raw["ad_number"],
        citation=raw["citation"], page_number_raw=raw["page_number"], summary=raw["summary"],
        col_r_raw=raw["col_r"], col_r_kind=col_r_kind(raw["col_r"]), drs_url=raw["drs_url"],
        comments=raw["comments"], flags=flags,
    )


_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def citation_date(s):
    """Date written in the Citation text cell (ISO) or None."""
    m = re.search(r"(%s) (\d{1,2}), (\d{4})" % _MONTHS, s or "")
    return dt.datetime.strptime(m.group(0), "%B %d, %Y").date().isoformat() if m else None
