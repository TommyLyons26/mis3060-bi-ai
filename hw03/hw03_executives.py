"""
Script:      hw03_executives.py
Source:      SEC EDGAR (submissions API + 8-K Item 5.02 filings)
Author:      Tommy Lyons
Generated:   2026-09-27

Executive events pipeline (Specification B). For five large-cap companies,
finds every 8-K filed in the past 12 months that reports Item 5.02
(Departure of Directors or Certain Officers; Election of Directors;
Appointment of Certain Officers), downloads the 8-K, strips it to plain
text, and extracts one row per person affected: event type (departure /
appointment / both), full name, title and effective date.

  - "both" means the SAME person leaves one role and takes another in the
    same filing (e.g. CEO -> Executive Chair).
  - A filing with a departure of one person and an appointment of another
    produces two separate rows.
  - A company with no Item 5.02 filings in the window prints
    "[Ticker]: No executive events in past 12 months" (valid data, not an error).
  - Fields that cannot be extracted are stored as "NOT_FOUND".

Run from the repo root:   python hw03/hw03_executives.py
"""

import csv
import datetime
import os
import re
import time

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
USER_AGENT = "MIS3060 Villanova tlyons01@villanova.edu"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

COMPANIES = [
    {"company": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart Inc.", "ticker": "WMT", "cik": "0000104169"},
]

LOOKBACK_DAYS = 365
NOT_FOUND = "NOT_FOUND"
REQUEST_PAUSE = 0.2  # SEC allows max 10 requests/second; stay well under it

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "executive_events.csv")
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
               "person_name", "title", "effective_date"]

# One shared session so the User-Agent header is sent on EVERY request
session = requests.Session()
session.headers.update(HEADERS)


def get(url):
    """GET a URL with the SEC User-Agent, pausing to respect rate limits."""
    time.sleep(REQUEST_PAUSE)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# Step 2: find Item 5.02 8-K filings from the past 12 months
# ---------------------------------------------------------------------------
def get_executive_filings(cik, cutoff):
    """Return all 8-K filings with Item 5.02 filed on/after `cutoff`
    (YYYY-MM-DD), newest first.

    The submissions API's "recent" block holds only the latest ~1,000
    filings. Frequent filers (JPM files hundreds of prospectuses) can push
    12 months of history into the older pages listed under
    filings["files"], so those pages are loaded too when they overlap
    the window."""
    data = get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    blocks = [data["filings"]["recent"]]
    for page in data["filings"].get("files", []):
        if page.get("filingTo", "") >= cutoff:
            blocks.append(get(f"https://data.sec.gov/submissions/{page['name']}").json())

    filings, seen = [], set()
    for block in blocks:
        # Each block is a set of parallel lists (form[i], items[i], ...)
        for i, form in enumerate(block["form"]):
            filing_date = block["filingDate"][i]
            items = [x.strip() for x in block["items"][i].split(",")]
            if form != "8-K" or filing_date < cutoff or "5.02" not in items:
                continue
            accession = block["accessionNumber"][i]
            if accession in seen:
                continue
            seen.add(accession)
            filings.append({
                "accession": accession,
                "filing_date": filing_date,
                "primary_doc": block["primaryDocument"][i],
            })
    filings.sort(key=lambda f: f["filing_date"], reverse=True)
    return filings


# ---------------------------------------------------------------------------
# Step 3a: download the 8-K and strip HTML
# ---------------------------------------------------------------------------
def filing_document_url(cik, filing):
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{filing['accession'].replace('-', '')}"
    return f"{folder}/{filing['primary_doc']}"


def html_to_text(html):
    """Strip HTML tags and normalise whitespace/punctuation to plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    for old, new in {"\xa0": " ", "’": "'", "‘": "'", "“": '"',
                     "”": '"', "—": "-", "–": "-"}.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


ITEM_502 = re.compile(r"\bItem\s*5\.02\b\.?", re.I)
NEXT_SECTION = re.compile(r"\bItem\s*\d{1,2}\.\d{2}\b|\bSIGNATURES?\b")
ITEM_502_HEADING = re.compile(
    r"^\W*Departure of Directors.*?Compensatory Arrangements of Certain Officers\W*", re.I)


def item_502_section(text):
    """Return just the Item 5.02 part of the 8-K (up to the next Item or
    the signature block). Falls back to the whole document."""
    for m in ITEM_502.finditer(text):
        rest = text[m.end():]
        stop = NEXT_SECTION.search(rest)
        body = ITEM_502_HEADING.sub("", rest[:stop.start()] if stop else rest).strip()
        if len(body) > 100:  # skip short cross-references like "see Item 5.02"
            return body
    return text


# ---------------------------------------------------------------------------
# Step 3b: sentence splitting and person-name detection
# ---------------------------------------------------------------------------
def split_sentences(text):
    """Split on sentence-ending punctuation without breaking on 'Mr.',
    'Inc.' or middle initials like 'Carlos A. Rodriguez'."""
    protected = re.sub(r"\b(Mr|Ms|Mrs|Dr|Jr|Sr|Inc|Co|Corp|Ltd|No|St)\.", r"\1§", text)
    protected = re.sub(r"\b([A-Z])\.", r"\1§", protected)
    parts = re.split(r"(?<=[.!?])\s+(?=[\"(]?[A-Z])", protected)
    return [p.replace("§", ".").strip() for p in parts if p.strip()]


NAME_TOKEN = r"(?:[A-Z]')?[A-Z][a-z]+(?:[A-Z][a-z]+)?(?:-[A-Z][a-z]+)?|[A-Z]\."
TOKEN_RUN = re.compile(rf"(?:{NAME_TOKEN})(?: (?:{NAME_TOKEN}))*")
HONORIFIC = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\. ((?:[A-Z]')?[A-Z][a-z]+(?:[A-Z][a-z]+)?(?:-[A-Z][a-z]+)?)")

# Capitalised words that are never part of a person's name in these filings
STOP_WORDS = set("""
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
on the a an in of and as at by for from to with effective following upon after prior
mr ms mrs dr jr sr he she his her their we our this that such there any also age
company firm board directors director committee corporation inc co corp llc ltd group
chief executive officer officers president presidents vice senior executive chair chairman
chairwoman lead independent general counsel annual special meeting shareholders stockholders
item section exhibit form regulation plan agreement agreements compensation audit nominating
governance transition date financial operating accounting technology finance human resources
legal global international north america american united states bank banking commercial
investment consumer community asset wealth management hardware software engineering services
retail operations markets corporate assistant controller treasurer secretary principal
restricted stock units unit equity incentive standard new york delaware washington california
arkansas texas santa clara cupertino redmond bentonville vp svp evp ceo cfo coo cto cao
club store stores division segment officer's report current former interim acting
worldwide field sales marketing affairs relations development strategy products
""".split())

# Words that end a department / organisation name. A run of capitalised words
# directly followed by one of these ("Worldwide Field Operations") is part of a
# job title, not a person's name.
ORG_WORDS = set("""
operations group division committee plan bank banking services markets engineering
sales marketing affairs relations development strategy products solutions technology
technologies club center foundation university partners officer counsel
""".split())


def find_names(sentence, company_words):
    """Return [(start, end, full_name)] for person names in a sentence:
    runs of 2-4 capitalised words, split at words that are never names."""
    stops = STOP_WORDS | company_words
    names = []
    for run in TOKEN_RUN.finditer(sentence):
        pos = run.start()
        chunk = []  # [(start, end, word)]
        for word in run.group().split(" ") + [None]:  # None flushes last chunk
            is_initial = word is not None and re.fullmatch(r"[A-Z]\.", word)
            if word is None or (not is_initial and word.lower() in stops):
                part_of_org = word is not None and word.lower() in ORG_WORDS
                if 2 <= len(chunk) <= 4 and not part_of_org and not chunk[-1][2].endswith(".") \
                        and sum(not w.endswith(".") for _, _, w in chunk) >= 2:
                    names.append((chunk[0][0], chunk[-1][1], " ".join(w for _, _, w in chunk)))
                chunk = []
            else:
                chunk.append((pos, pos + len(word), word))
            if word is not None:
                pos += len(word) + 1
    return names


def name_tokens(name):
    """Name words without middle initials: 'John R. Furner' -> ['John', 'Furner']."""
    return [t for t in name.split() if not re.fullmatch(r"[A-Z]\.", t)]


def make_resolver(full_names):
    """Return a function that maps any reference to a person onto the fullest
    form of their name used in the filing, so one person = one row:
      'Di Sibio'     -> 'Carmine Di Sibio'      (two-word surname)
      'Nora Johnson' -> 'Suzanne Nora Johnson'
      'Furner'       -> 'John R. Furner'        (from 'Mr. Furner')
      'John Furner'  -> 'John R. Furner'        (same first + last name)"""
    candidates = sorted(set(full_names), key=lambda n: -len(n.split()))

    def resolve(name):
        toks = name_tokens(name)
        for cand in candidates:
            ct = name_tokens(cand)
            if len(ct) < len(toks) or not toks:
                continue
            if ct[-len(toks):] == toks or (len(toks) >= 2 and ct[0] == toks[0] and ct[-1] == toks[-1]):
                return cand
        return name
    return resolve


def find_people(sentence, company_words, resolve):
    """Full names plus 'Mr./Ms./Dr. Surname' references, each resolved to the
    full name used elsewhere in the section."""
    names = find_names(sentence, company_words)
    people = [(s, e, resolve(n)) for s, e, n in names]
    for m in HONORIFIC.finditer(sentence):
        # "Mr. John R. Furner" / "Ms. Nora Johnson": the full name after the
        # honorific was already found above, so skip the partial match
        if any(m.start() <= s <= m.end() for s, _, _ in names):
            continue
        people.append((m.start(), m.end(), resolve(m.group(1))))
    return sorted(people)


# ---------------------------------------------------------------------------
# Step 3c: event keywords, title and effective date
# ---------------------------------------------------------------------------
# "transition from his role as CEO to Executive Chair" -> both
BOTH_RE = re.compile(
    r"\btransition(?:s|ed|ing)? from (?:his|her|their) (?:role|position)s? as (?:the )?"
    r"(?P<old>[^,;]+?) to (?:the (?:role|position) of )?(?P<new>[^,;(]+?)"
    r"(?=\s*[,;(.]|\s+effective|\s+on\s|$)", re.I)

DEPARTURE_RE = re.compile(
    r"\b(?:retir(?:e|es|ed|ing)|retirement(?! (?:plan|savings|benefit|account|program))"
    r"|resign(?:s|ed|ing|ation)?|step(?:s|ped|ping)? down|depart(?:s|ed|ure)?"
    r"|leav(?:e|es|ing) the (?:Company|Firm|Board)|not (?:to )?stand for re-?election"
    r"|will not stand|terminat(?:e|ed|ion)|separat(?:e|ed|ion) from|cease[sd]? to serve"
    r"|transition(?:s|ed|ing)? (?:of (?:duties|responsibilities) )?from)\b", re.I)

APPOINTMENT_RE = re.compile(
    r"\b(?:appoint(?:s|ed)?|(?<!re-)(?<!re)elect(?:s|ed)?|named(?! executive officer)"
    r"|promot(?:es|ed)|hire[sd]?|nominat(?:es|ed)|select(?:s|ed)"
    r"|will join|to join|join(?:s|ed)? (?:the Company|the Firm|the Board) as"
    r"|(?:will |to )?become[s]?|became|will serve as|will assume|assumed the role)\b", re.I)

SUCCEED_RE = re.compile(r"\bsucceed(?:s|ed|ing)?\b", re.I)

ROLE_WORDS = re.compile(
    r"\b(?:officer|president|director|chair\w*|counsel|ceo|cfo|coo|cao|cto|cio|clo|vp|svp"
    r"|evp|controller|treasurer|secretary|head|member|board|co-?presidents?|co-?ceos?)\b", re.I)

TITLE_END = (r"(?=\s*[,;(]|\s+effective|\s+on\s|\s+in\s+(?:each|[A-Z])|\s+until|\s+upon"
             r"|\s+since|\s+following|\s+reporting|\s+to\s+(?:pursue|focus)|\.\s|\.$|$)")
TITLE_LEAD = r"(?:(?:the|a|an|its|our|new|current)\s+)*(?:[A-Z][\w&.]*'s\s+)?"
TITLE_DIRECT = re.compile(
    rf"^(?!\s*(?:from|with|to|his|her|their|that|of)\b)\s*(?:as\s+)?{TITLE_LEAD}(?P<t>[^,;(]+?){TITLE_END}")
TITLE_AS = re.compile(rf"\bas\s+{TITLE_LEAD}(?P<t>[^,;(]+?){TITLE_END}")
TITLE_APPOSITIVE = re.compile(rf"^,\s*{TITLE_LEAD}(?P<t>[^,;(]+?)(?=\s*[,(])")
RESIGNED_FROM_BOARD = re.compile(r"^\s*(?:from|to|as a member of) (?:the|its|our) Board\b(?!'s)", re.I)

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = rf"(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}}"
EFFECTIVE_DATE = re.compile(rf"\beffective\b[^.;]{{0,80}}?({DATE})", re.I)
LEAD_DATE = re.compile(rf"^\W*(?:\([a-z]\)\s*)?On ({DATE})")
DEFINED_DATE = re.compile(rf"({DATE})\s*\(the \"([^\"]+)\"\)")

COORDINATED = re.compile(r"^(?:,\s*(?:age\s+)?\d{2})?,?\s+and\s+$")
OBJECT_GAP = re.compile(r"^\s{0,2}(?:of\s+)?(?:(?:Mr|Ms|Mrs|Dr)\.\s+)?$")


def iso_date(text):
    return datetime.datetime.strptime(re.sub(r"\s+", " ", text), "%B %d, %Y").strftime("%Y-%m-%d")


def clean_title(title, company_words):
    title = re.sub(r"\s+", " ", title).strip(" .,'\"")
    # Drop a trailing "of the Company" / "of Microsoft Corporation" etc.
    names = "|".join(re.escape(w) for w in company_words) or "Company"
    title = re.sub(rf"\s+of\s+(?:the\s+)?(?:Company|Firm|(?i:{names})\b.*)$", "", title)
    return title[:100]


def find_title(sentence, kw_end, person_end, company_words):
    """Title for one event, trying the most specific patterns first."""
    after_kw = sentence[max(kw_end, person_end):]  # skip the name if it follows the verb
    if RESIGNED_FROM_BOARD.match(after_kw):
        return "Director"
    candidates = []
    m = TITLE_DIRECT.match(after_kw)
    if m:
        candidates.append(m.group("t"))
    candidates += [m.group("t") for m in TITLE_AS.finditer(after_kw)]
    m = TITLE_APPOSITIVE.match(sentence[person_end:])  # "Jane Doe, Chief X Officer, ..."
    if m:
        candidates.append(m.group("t"))
    for title in candidates:
        if ROLE_WORDS.search(title):
            return clean_title(title, company_words)
    return NOT_FOUND


def find_effective_date(sentence, kw_start, defined_dates, filing_date):
    """Effective date for one event, as YYYY-MM-DD."""
    tail = sentence[kw_start:]
    for text in (tail, sentence):
        m = EFFECTIVE_DATE.search(text)
        if m:
            return iso_date(m.group(1))
    for term, date in defined_dates.items():          # "on the Transition Date"
        if re.search(rf"\b{re.escape(term)}\b", tail):
            return date
    if re.search(r"\b(?:effective )?immediately\b", sentence, re.I):
        lead = LEAD_DATE.search(sentence)
        return iso_date(lead.group(1)) if lead else filing_date
    m = re.search(DATE, tail)                          # "will become X on March 1, 2026"
    if m:
        return iso_date(m.group(0))
    return NOT_FOUND


def keyword_hits(sentence):
    """[(start, end, kind, both_match)] for event keywords in a sentence.
    'both' phrases are matched first and masked so their words are not
    re-counted as a plain departure."""
    hits, masked = [], []
    for m in BOTH_RE.finditer(sentence):
        hits.append((m.start(), m.end(), "both", m))
        masked.append((m.start(), m.end()))

    def free(m):
        return all(m.end() <= s or m.start() >= e for s, e in masked)

    for regex, kind in ((SUCCEED_RE, "succeed"), (DEPARTURE_RE, "departure"),
                        (APPOINTMENT_RE, "appointment")):
        for m in regex.finditer(sentence):
            if free(m):
                hits.append((m.start(), m.end(), kind, None))
                masked.append((m.start(), m.end()))
    return sorted(hits)


def pick_targets(sentence, people, kw_start, kw_end, kind):
    """Decide who a keyword refers to: a name immediately after the verb
    ("the Board appointed Jane Doe") or else the nearest name before it
    ("Jane Doe will retire"). Names joined by 'and' are included too."""
    obj = next((p for p in people if p[0] >= kw_end
                and OBJECT_GAP.match(sentence[kw_end:p[0]])), None)
    subj = next((p for p in reversed(people) if p[1] <= kw_start), None)

    targets = []  # [(person, event_type)]
    if kind == "succeed":          # "A will succeed B": A appointed, B departs
        if subj:
            targets.append((subj, "appointment"))
        if obj:
            targets.append((obj, "departure"))
        return targets
    chosen = obj if (obj and kind != "both") else subj
    if not chosen:
        return targets
    group = [chosen]
    idx = people.index(chosen)
    # "Doug Petno, 61, and Troy Rohrbaugh" -> both names get the event
    step = -1 if chosen is subj else 1
    j = idx + step
    while 0 <= j < len(people):
        a, b = (people[j], group[-1]) if step == -1 else (group[-1], people[j])
        if not COORDINATED.match(sentence[a[1]:b[0]]):
            break
        group.append(people[j])
        j += step
    return [(p, kind) for p in group]


def extract_events(document_text, company, filing_date):
    """Return a list of events {event_type, person_name, title, effective_date}
    from the Item 5.02 section of an 8-K, one per person."""
    section = item_502_section(document_text)
    company_words = {w.lower().strip(".,&") for w in company.split() if len(w) > 2}
    sentences = split_sentences(section)

    resolve = make_resolver(full for s in sentences for _, _, full in find_names(s, company_words))
    defined_dates = {term: iso_date(d) for d, term in DEFINED_DATE.findall(section)}

    events = {}  # person_name -> event dict (insertion-ordered)
    for s in sentences:
        people = find_people(s, company_words, resolve)
        if not people:
            continue
        for kw_start, kw_end, kind, both_match in keyword_hits(s):
            for (p_start, p_end, name), event_type in pick_targets(s, people, kw_start, kw_end, kind):
                if both_match:
                    old = clean_title(both_match.group("old"), company_words)
                    new = clean_title(both_match.group("new"), company_words)
                    title = f"{old} -> {new}"
                else:
                    title = find_title(s, kw_end, p_end, company_words)
                date = find_effective_date(s, kw_start, defined_dates, filing_date)

                ev = events.setdefault(name, {"types": set(), "title": NOT_FOUND,
                                              "effective_date": NOT_FOUND})
                ev["types"].add(event_type)
                if ev["title"] == NOT_FOUND:
                    ev["title"] = title
                if ev["effective_date"] == NOT_FOUND:
                    ev["effective_date"] = date

    results = []
    for name, ev in events.items():
        types = ev["types"]
        if "both" in types or {"departure", "appointment"} <= types:
            event_type = "both"
        else:
            event_type = types.pop()
        results.append({"event_type": event_type, "person_name": name,
                        "title": ev["title"], "effective_date": ev["effective_date"]})
    return results


# ---------------------------------------------------------------------------
# Step 5: printing
# ---------------------------------------------------------------------------
def print_row(row):
    print(f"{row['ticker']} | {row['filing_date']} | {row['event_type']} | "
          f"{row['person_name']} | {row['title']}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    cutoff = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    print(f"Item 5.02 8-K filings from {cutoff} to today\n")

    rows = []
    for co in COMPANIES:
        try:
            filings = get_executive_filings(co["cik"], cutoff)
        except requests.RequestException as err:
            print(f"{co['ticker']}: could not load submissions ({err})")
            continue

        # Step 6: zero filings is valid data, not an error
        if not filings:
            print(f"{co['ticker']}: No executive events in past 12 months")
            continue

        for filing in filings:
            base = {"company": co["company"], "ticker": co["ticker"],
                    "cik": co["cik"], "filing_date": filing["filing_date"]}
            try:
                html = get(filing_document_url(co["cik"], filing)).text
                events = extract_events(html_to_text(html), co["company"], filing["filing_date"])
            except requests.RequestException as err:
                print(f"{co['ticker']}: failed to download filing {filing['accession']} ({err})")
                events = []

            # Keep the filing in the dataset even if no event could be parsed
            if not events:
                events = [{"event_type": NOT_FOUND, "person_name": NOT_FOUND,
                           "title": NOT_FOUND, "effective_date": NOT_FOUND}]

            # Step 4: one row per event
            for event in events:
                row = {**base, **event}
                print_row(row)
                rows.append(row)

    # Step 7: save
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {os.path.relpath(OUTPUT_CSV)}")


if __name__ == "__main__":
    main()
