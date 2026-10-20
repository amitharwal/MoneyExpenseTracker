"""Bank statement import: parse CSV/OFX, clean descriptions, categorize, de-duplicate."""
import csv
import hashlib
import io
import re
import string
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from config import DEFAULT_KEYWORDS, EXPENSE_CATEGORIES, INCOME_CATEGORIES
from models import Rule, Transaction, db

DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y", "%Y/%m/%d",
    "%m-%d-%Y", "%d-%m-%Y", "%b %d, %Y", "%d %b %Y", "%d-%b-%Y", "%Y%m%d",
]

# --- Description cleanup -----------------------------------------------------

_PREFIXES = re.compile(
    r"^(?:pos (?:purchase|debit)|debit card purchase|purchase authorized on \d{1,2}/\d{1,2}|"
    r"checkcard \d{4}|recurring payment|ach (?:debit|credit)|online payment|card purchase|"
    r"visa purchase|debit purchase|purchase|sq \*|tst\* ?|pp\*|paypal \*|sp \*|cko\*|in \*|bt\*)\s*",
    re.I,
)
_NOISE = [
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),        # dates
    re.compile(r"\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}"),          # phone numbers
    re.compile(r"#\s?\w+"),                                  # store numbers
    re.compile(r"\b(?:x+|\*+)\d{2,}\b", re.I),               # masked card numbers
    re.compile(r"\b[a-z]*\d[\w-]{3,}\b", re.I),              # reference codes
    re.compile(r"\b\d{3,}\b"),                               # long digit runs
    re.compile(r"\s+[A-Z]{2}$"),                             # trailing state code
]


_ALIASES = {"amzn": "Amazon", "amazon mktp": "Amazon", "amzn mktp": "Amazon", "wm supercenter": "Walmart", "wal-mart": "Walmart"}


def clean_description(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = _PREFIXES.sub("", s)
    # "UBER *TRIP HELP.UBER.COM" -> "UBER"; "AMZN Mktp US*2K3LX0" -> "AMZN Mktp US"
    if "*" in s:
        left, right = s.split("*", 1)
        s = left if len(re.sub(r"[^a-z]", "", left, flags=re.I)) >= 3 else right
    s = re.sub(r"\.(?:com|net|org|co|io)\b.*$", "", s, flags=re.I)
    for pattern in _NOISE:
        s = pattern.sub(" ", s)
    s = re.sub(r"\b(\w{2,}) S\b", r"\1's", s)  # "TRADER JOE S" -> "TRADER JOE'S"
    s = re.sub(r"\s+", " ", s).strip(" -*.,:;/")
    if not s:
        return (raw or "").strip()[:140]
    lowered = s.lower()
    for alias, name in _ALIASES.items():
        if lowered == alias or lowered.startswith(alias + " "):
            return name
    return string.capwords(lowered)[:140]


def merchant_key(raw: str) -> str:
    """Short lowercase key used for learned rules, e.g. "trader joe's"."""
    words = [w for w in re.sub(r"[^a-z&' ]", " ", clean_description(raw).lower()).split() if len(w) > 1]
    return " ".join(words[:2])


def _haystack(raw: str) -> str:
    return " " + re.sub(r"\s+", " ", clean_description(raw).lower() + " " + (raw or "").lower()) + " "


# --- Categorization ------------------------------------------------------------

class Categorizer:
    """Learned rules first (longest pattern wins), then built-in keywords."""

    def __init__(self):
        self.rules = sorted(Rule.query.all(), key=lambda r: len(r.pattern), reverse=True)

    def suggest(self, raw: str, kind: str):
        hay = _haystack(raw)
        for rule in self.rules:
            if rule.kind == kind and rule.pattern in hay:
                return {"category": rule.category, "rename": rule.rename, "via": "rule", "rule_id": rule.id}
        for k, category, words in DEFAULT_KEYWORDS:
            if k == kind and any(w in hay for w in words):
                return {"category": category, "rename": None, "via": "keyword", "rule_id": None}
        return {"category": "Other", "rename": None, "via": None, "rule_id": None}


def learn_rule(raw: str, kind: str, category: str, rename: str | None = None):
    """Remember a category choice for this merchant (creates or updates a rule)."""
    key = merchant_key(raw)
    if len(key) < 3 or category == "Other":
        return None
    rule = Rule.query.filter_by(pattern=key).first()
    if rule:
        rule.kind, rule.category = kind, category
        if rename:
            rule.rename = rename
    else:
        rule = Rule(pattern=key, kind=kind, category=category, rename=rename or None)
        db.session.add(rule)
    return rule


# --- Parsing -----------------------------------------------------------------------

def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def is_ofx(text: str) -> bool:
    head = text[:2000].upper()
    return "<OFX>" in head or "OFXHEADER" in head or "<STMTTRN>" in text.upper()


def parse_amount(value) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")") or s.endswith("-") or s.upper().endswith(" DR")
    s = re.sub(r"[^\d.,\-]", "", s)
    if s.count(",") and s.count("."):
        s = s.replace(",", "")  # 1,234.56
    elif s.count(",") == 1 and len(s.split(",")[1]) == 2:
        s = s.replace(",", ".")  # 12,50 (European)
    else:
        s = s.replace(",", "")
    try:
        amount = Decimal(s.rstrip("-") or "0")
    except InvalidOperation:
        return None
    return -abs(amount) if negative else amount


def parse_date(value: str, fmt: str) -> date | None:
    try:
        return datetime.strptime(str(value).strip(), fmt).date()
    except ValueError:
        return None


def read_csv(text: str):
    """Return (headers, rows), skipping any preamble lines above the real header."""
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("That file looks empty.")
    width = Counter(len(r) for r in rows).most_common(1)[0][0]
    pad = lambda r: r + [""] * (width - len(r))
    for i, row in enumerate(rows):
        # Preamble lines ("Account: ...") are narrower. Allow one column of slack:
        # some banks (e.g. Chase) end every data row with a stray trailing comma.
        if len(row) < width - 1:
            continue
        if _looks_like_data(row):
            # No header row at all: name the columns by position
            return [f"Column {j + 1}" for j in range(width)], [pad(r) for r in rows[i:] if len(r) >= width - 1]
        headers = [h.strip() or f"Column {j + 1}" for j, h in enumerate(pad(row))]
        return headers, [pad(r) for r in rows[i + 1:] if len(r) >= width - 1]
    return [f"Column {j + 1}" for j in range(width)], rows


_MONEY = re.compile(r"^[-+(]?\$?[\d,]*\d\.\d{2}\)?-?$")


def _looks_like_data(row) -> bool:
    return any(guess_date_format([c]) or _MONEY.match(c.strip()) for c in row if c.strip())


def header_signature(headers) -> str:
    return hashlib.sha256("|".join(h.strip().lower() for h in headers).encode()).hexdigest()[:32]


def _find(headers, *needles, exclude=()):
    lowered = [h.lower() for h in headers]
    for needle in needles:
        for i, h in enumerate(lowered):
            if needle in h and not any(x in h for x in exclude):
                return i
    return None


def guess_mapping(headers, rows):
    m = {
        "date": _find(headers, "transaction date", "trans date", "posted date", "posting date", "date"),
        "description": _find(headers, "description", "payee", "merchant", "name", "details", "memo", "narrative"),
        "amount": _find(headers, "amount", "amt", exclude=("balance",)),
        "debit": _find(headers, "debit", "withdrawal", "money out", "paid out"),
        "credit": _find(headers, "credit", "deposit", "money in", "paid in"),
        "date_format": None,
        "invert": False,
    }
    if m["amount"] is not None and m["debit"] is not None and m["amount"] in (m["debit"], m["credit"]):
        m["amount"] = None
    if m["debit"] is not None and m["credit"] is not None:
        m["amount"] = None
    else:
        m["debit"] = m["credit"] = None
    if m["date"] is None or m["description"] is None or (m["amount"] is None and m["debit"] is None):
        _guess_by_content(m, headers, rows)
    if m["date"] is not None:
        m["date_format"] = guess_date_format([r[m["date"]] for r in rows[:50] if m["date"] < len(r)])
    if m["amount"] is not None:
        amounts = [parse_amount(r[m["amount"]]) for r in rows[:200] if m["amount"] < len(r)]
        amounts = [a for a in amounts if a]
        # Card exports often list charges as positive numbers
        m["invert"] = bool(amounts) and sum(a > 0 for a in amounts) / len(amounts) > 0.8
    return m


def _guess_by_content(m, headers, rows):
    sample = rows[:30]
    for i in range(len(headers)):
        col = [r[i] for r in sample if i < len(r) and r[i].strip()]
        if not col:
            continue
        if m["date"] is None and guess_date_format(col):
            m["date"] = i
        elif m["amount"] is None and m["debit"] is None and all(parse_amount(c) is not None for c in col) \
                and all(re.search(r"\d", c) for c in col):
            m["amount"] = i
        elif m["description"] is None and sum(bool(re.search(r"[a-z]{3}", c, re.I)) for c in col) > len(col) / 2:
            m["description"] = i


def guess_date_format(values):
    """The format that reads the most values (junk rows like totals are tolerated).
    Ties go to the earlier, more common format, e.g. US month-first."""
    values = [v.strip() for v in values if v and v.strip()]
    if not values:
        return None
    best, best_hits = None, 0
    for fmt in DATE_FORMATS:
        hits = sum(parse_date(v, fmt) is not None for v in values)
        if hits > best_hits:
            best, best_hits = fmt, hits
    return best if best_hits >= max(1, len(values) * 0.6) else None


def apply_mapping(rows, m):
    """Turn raw CSV rows into records using a column mapping."""
    out = []
    for n, r in enumerate(rows):
        def cell(key):
            i = m.get(key)
            return r[i] if i is not None and i < len(r) else ""

        d = parse_date(cell("date"), m.get("date_format") or "%Y-%m-%d")
        raw = cell("description").strip()
        if m.get("amount") is not None:
            amount = parse_amount(cell("amount"))
            if amount is not None and m.get("invert"):
                amount = -amount
        else:
            debit, credit = parse_amount(cell("debit")), parse_amount(cell("credit"))
            amount = (abs(credit) if credit else Decimal(0)) - (abs(debit) if debit else Decimal(0))
            if not debit and not credit:
                amount = None
        error = None
        if d is None:
            error = "Couldn't read the date"
        elif amount is None or amount == 0:
            error = "No amount"
        elif not raw:
            error = "No description"
        out.append({"row": n, "date": d, "raw": raw, "amount": amount, "error": error, "fitid": None})
    return out


def parse_ofx(text: str):
    out = []
    for n, block in enumerate(re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|</BANKTRANLIST>)", text, re.S | re.I)):
        def tag(name):
            hit = re.search(rf"<{name}>([^<\r\n]*)", block, re.I)
            return hit.group(1).strip() if hit else ""

        d = parse_date(tag("DTPOSTED")[:8], "%Y%m%d")
        amount = parse_amount(tag("TRNAMT"))
        name, memo = tag("NAME"), tag("MEMO")
        raw = name if name and not memo.lower().startswith(name.lower()) else (memo or name)
        if name and memo and memo.lower() != name.lower() and not memo.lower().startswith(name.lower()):
            raw = f"{name} {memo}"
        error = None if d and amount else "Couldn't read this entry"
        out.append({"row": n, "date": d, "raw": raw.strip(), "amount": amount, "error": error, "fitid": tag("FITID") or None})
    if not out:
        raise ValueError("No transactions found in that OFX/QFX file.")
    return out


# --- Preview & commit -----------------------------------------------------------------

# Money moving between your own accounts isn't income or spending
_TRANSFER = re.compile(
    r"payment thank you|autopay|auto pay|online transfer|transfer (?:to|from)|xfer|"
    r"credit card payment|card payment|payment to (?:chase|amex|citi|discover|capital one)|"
    r"epay|ach pmt|venmo cashout|zelle (?:to|from) (?:self|me)",
    re.I,
)

def fingerprint(rec, occurrence: int) -> str:
    if rec["fitid"]:
        basis = f"ofx|{rec['fitid']}|{rec['date']}|{rec['amount']}"
    else:
        basis = f"csv|{rec['date']}|{rec['amount']}|{merchant_key(rec['raw']) or rec['raw'].lower()}|{occurrence}"
    return hashlib.sha256(basis.encode()).hexdigest()


def build_preview(records):
    cat = Categorizer()
    seen = Counter()
    hashes = []
    for rec in records:
        if rec["error"]:
            hashes.append(None)
            continue
        key = (rec["date"], rec["amount"], merchant_key(rec["raw"]))
        seen[key] += 1
        hashes.append(fingerprint(rec, seen[key]))

    existing = {h for (h,) in db.session.query(Transaction.import_hash).filter(
        Transaction.import_hash.in_([h for h in hashes if h])
    )} if any(hashes) else set()

    # Manually entered transactions on the same day for the same amount are likely the same thing
    dates = [r["date"] for r in records if r["date"]]
    manual = Counter()
    if dates:
        for t in Transaction.query.filter(
            Transaction.import_hash.is_(None),
            Transaction.occurred_on.between(min(dates), max(dates)),
        ):
            manual[(t.occurred_on, t.signed)] += 1

    items = []
    for rec, h in zip(records, hashes):
        if rec["error"]:
            items.append({"row": rec["row"], "raw": rec["raw"], "error": rec["error"], "include": False})
            continue
        kind = "income" if rec["amount"] > 0 else "expense"
        s = cat.suggest(rec["raw"], kind)
        status = "new"
        if h in existing:
            status = "imported"
        elif manual.get((rec["date"], rec["amount"])):
            manual[(rec["date"], rec["amount"])] -= 1
            status = "possible"
        elif _TRANSFER.search(rec["raw"]) and s["via"] != "rule":
            status = "transfer"
        items.append({
            "row": rec["row"],
            "date": rec["date"].isoformat(),
            "raw": rec["raw"],
            "note": s["rename"] or clean_description(rec["raw"]),
            "kind": kind,
            "amount": float(abs(rec["amount"])),
            "category": s["category"],
            "suggested": s["category"],
            "via": s["via"],
            "hash": h,
            "status": status,
            "include": status == "new",
        })
    return items


def commit_items(items):
    """Insert the reviewed rows. Returns (imported, skipped, rules_learned)."""
    cat_sets = {"income": set(INCOME_CATEGORIES), "expense": set(EXPENSE_CATEGORIES)}
    hashes = [i.get("hash") for i in items if i.get("hash")]
    existing = {h for (h,) in db.session.query(Transaction.import_hash).filter(Transaction.import_hash.in_(hashes))}
    imported = skipped = learned = 0
    today = date.today()
    for item in items:
        h = item.get("hash")
        kind = item.get("kind")
        category = item.get("category")
        try:
            d = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
            amount = Decimal(str(item.get("amount"))).quantize(Decimal("0.01"))
        except (ValueError, InvalidOperation):
            skipped += 1
            continue
        if not h or h in existing or kind not in cat_sets or category not in cat_sets[kind] or amount <= 0 or d > today:
            skipped += 1
            continue
        raw = str(item.get("raw", ""))[:255]
        note = str(item.get("note") or clean_description(raw)).strip()[:140]
        db.session.add(Transaction(
            kind=kind, amount=amount, category=category, note=note, occurred_on=d,
            source="import", raw_description=raw, import_hash=h,
        ))
        existing.add(h)
        imported += 1
        # The user corrected our guess: remember it for next time
        if category != item.get("suggested") or (note != clean_description(raw) and item.get("renamed")):
            if learn_rule(raw, kind, category, note if item.get("renamed") else None):
                learned += 1
    return imported, skipped, learned
