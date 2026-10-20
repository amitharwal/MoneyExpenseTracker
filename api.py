import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import tempfile
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import func, or_
from werkzeug.exceptions import HTTPException

import demo
import importer
import storage
from config import DATA_DIR, DB_PATH, EXPENSE_CATEGORIES, INCOME_CATEGORIES
from models import Budget, ImportProfile, Recurring, Rule, Transaction, add_month, db

api = Blueprint("api", __name__, url_prefix="/api")

RANGES = ["1M", "3M", "6M", "YTD", "1Y", "ALL"]
RANGE_DAYS = {"1M": 30, "3M": 91, "6M": 182, "1Y": 365}
MAX_POINTS = 240


class BadRequest(Exception):
    status = 400


class NotFound(BadRequest):
    status = 404


@api.errorhandler(BadRequest)
def _bad_request(err):
    return jsonify(error=str(err)), err.status


@api.errorhandler(Exception)
def _server_error(err):
    """Always answer the frontend in JSON so failures show up in the UI."""
    if isinstance(err, HTTPException):
        return jsonify(error=err.description), err.code
    db.session.rollback()
    current_app.logger.exception("API request failed")
    return jsonify(error="Couldn't save that. The server hit an error; check the server log."), 500


@api.before_request
def _daily_upkeep():
    """Log recurring items that have come due, and take today's backup if needed."""
    today = date.today()
    due = Recurring.query.filter(Recurring.active.is_(True), Recurring.next_date <= today).all()
    if due:
        for r in due:
            db.session.add_all(r.post_due(today))
        db.session.commit()
    storage.ensure_daily_backup()


# --- Parsing helpers -------------------------------------------------------

def _amount(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise BadRequest("Enter an amount.")
    if not Decimal("0.01") <= amount <= Decimal("9999999999.99"):
        raise BadRequest("Amount must be greater than $0.")
    return amount


def _kind_and_category(data):
    kind = data.get("kind")
    if kind not in ("income", "expense"):
        raise BadRequest("Choose income or expense.")
    allowed = INCOME_CATEGORIES if kind == "income" else EXPENSE_CATEGORIES
    category = data.get("category")
    if category not in allowed:
        raise BadRequest("Pick a category.")
    return kind, category


def _date(value, allow_future=False):
    try:
        d = datetime.strptime(value or "", "%Y-%m-%d").date()
    except ValueError:
        raise BadRequest("Enter a valid date.")
    if not allow_future and d > date.today():
        raise BadRequest("Date can't be in the future.")
    return d


def _note(data):
    return str(data.get("note", "")).strip()[:140]


def _month_bounds(d):
    first = d.replace(day=1)
    return first, first.replace(day=calendar.monthrange(d.year, d.month)[1])


def _fixed_by_category():
    """Monthly recurring expenses per category; these are due in full, not spread out."""
    fixed = defaultdict(Decimal)
    for r in Recurring.query.filter(Recurring.active.is_(True), Recurring.kind == "expense"):
        fixed[r.category] += r.amount
    return fixed


def _f(x):
    return float(x) if x is not None else None


def _change(now, before):
    return _f((now - before) / before * 100) if before else None


# --- Overview --------------------------------------------------------------

@api.get("/overview")
def overview():
    key = request.args.get("range", "3M")
    if key not in RANGES:
        key = "3M"

    today = date.today()
    txns = (
        Transaction.query
        .filter(Transaction.occurred_on <= today)
        .order_by(Transaction.occurred_on, Transaction.id)
        .all()
    )
    first = txns[0].occurred_on if txns else today

    # Balance series for the chart
    if key == "YTD":
        start = date(today.year, 1, 1)
    elif key == "ALL":
        start = min(first, today) - timedelta(days=1)
    else:
        start = today - timedelta(days=RANGE_DAYS[key])
    opening = sum((t.signed for t in txns if t.occurred_on < start), Decimal(0))
    daily = defaultdict(Decimal)
    for t in txns:
        if t.occurred_on >= start:
            daily[t.occurred_on] += t.signed
    series, balance = [], opening
    for i in range((today - start).days + 1):
        d = start + timedelta(days=i)
        balance += daily[d]
        series.append({"d": d.isoformat(), "v": float(balance)})
    if len(series) > MAX_POINTS:
        step = -(-len(series) // MAX_POINTS)
        last = series[-1]
        series = series[::step]
        if series[-1] is not last:
            series.append(last)

    # This month vs. the same days last month
    month_start, month_end = _month_bounds(today)
    prev_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_same_day = prev_start.replace(day=min(today.day, calendar.monthrange(prev_start.year, prev_start.month)[1]))
    month = {"income": Decimal(0), "spent": Decimal(0)}
    prev = {"income": Decimal(0), "spent": Decimal(0)}
    by_cat, prev_by_cat = defaultdict(Decimal), defaultdict(Decimal)
    for t in txns:
        d = t.occurred_on
        if d >= month_start:
            month["income" if t.kind == "income" else "spent"] += t.amount
            if t.kind == "expense":
                by_cat[t.category] += t.amount
        elif prev_start <= d < month_start:
            if t.kind == "expense":
                prev_by_cat[t.category] += t.amount
                if d <= prev_same_day:
                    prev["spent"] += t.amount
            elif d <= prev_same_day:
                prev["income"] += t.amount

    budgets = {b.category: b.amount for b in Budget.query}
    fixed = _fixed_by_category()
    categories = [
        {
            "name": cat,
            "spent": float(amount),
            "budget": _f(budgets.get(cat)),
            "fixed": float(fixed.get(cat, 0)),
            "last_month": float(prev_by_cat.get(cat, 0)),
        }
        for cat, amount in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # Upcoming recurring items in the next 30 days
    horizon = today + timedelta(days=30)
    upcoming = []
    for r in Recurring.query.filter(Recurring.active.is_(True)):
        d = r.next_date
        while d <= horizon:
            upcoming.append({**r.to_dict(), "date": d.isoformat()})
            d = add_month(d, r.day)
    upcoming.sort(key=lambda u: u["date"])
    due_this_month = [u for u in upcoming if u["date"] <= month_end.isoformat()]
    bills_left = sum(Decimal(str(u["amount"])) for u in due_this_month if u["kind"] == "expense")
    income_left = sum(Decimal(str(u["amount"])) for u in due_this_month if u["kind"] == "income")

    # Budget pace: what's left per remaining day
    days_in_month = month_end.day
    days_left = days_in_month - today.day + 1
    total_budget = sum(budgets.values(), Decimal(0))
    budgeted_spent = sum((by_cat.get(c, Decimal(0)) for c in budgets), Decimal(0))

    insights = _insights(month, prev, by_cat, prev_by_cat, budgets, today, days_left, total_budget, budgeted_spent)

    change = balance - opening
    return jsonify(
        range=key,
        balance=float(balance),
        opening=float(opening),
        change=float(change),
        change_pct=_change(balance, opening) if opening > 0 else None,
        series=series,
        month={
            "label": today.strftime("%B"),
            "day": today.day,
            "days": days_in_month,
            "income": float(month["income"]),
            "spent": float(month["spent"]),
            "net": float(month["income"] - month["spent"]),
            "spent_change": _change(month["spent"], prev["spent"]),
            "income_change": _change(month["income"], prev["income"]),
            "projected": float(balance - bills_left + income_left),
            "bills_left": float(bills_left),
            "income_left": float(income_left),
        },
        budget={
            "total": float(total_budget),
            "spent": float(budgeted_spent),
            "per_day": float(max(total_budget - budgeted_spent, 0) / days_left) if total_budget else None,
        },
        categories=categories,
        upcoming=upcoming[:6],
        recent=[t.to_dict() for t in reversed(txns[-6:])],
        insights=insights,
        has_any=bool(txns) or Recurring.query.count() > 0,
        has_demo=Transaction.query.filter_by(source="demo").count() > 0,
    )


def _insights(month, prev, by_cat, prev_by_cat, budgets, today, days_left, total_budget, budgeted_spent):
    out = []
    if prev["spent"]:
        diff = month["spent"] - prev["spent"]
        pct = abs(diff / prev["spent"] * 100)
        if pct >= 1:
            direction = "less" if diff < 0 else "more"
            out.append({
                "tone": "pos" if diff < 0 else "neg",
                "title": f"{pct:.0f}% {direction} spending",
                "body": f"You've spent ${abs(diff):,.0f} {direction} than at this point last month.",
            })

    over = [c for c, limit in budgets.items() if by_cat.get(c, 0) > limit]
    if over:
        out.append({
            "tone": "neg",
            "title": f"{len(over)} budget{'s' if len(over) > 1 else ''} over",
            "body": ", ".join(sorted(over)) + (" is" if len(over) == 1 else " are") + " past this month's limit.",
        })
    elif total_budget:
        left = total_budget - budgeted_spent
        out.append({
            "tone": "pos",
            "title": f"${max(left, 0) / days_left:,.0f}/day to stay on budget",
            "body": f"${max(left, 0):,.0f} left across your budgets for the next {days_left} days.",
        })

    growth = [
        (c, amt - prev_by_cat[c]) for c, amt in by_cat.items()
        if prev_by_cat.get(c) and amt > prev_by_cat[c]
    ]
    if growth:
        cat, delta = max(growth, key=lambda g: g[1])
        out.append({
            "tone": "neutral",
            "title": f"{cat} is up ${delta:,.0f}",
            "body": f"Already more than all of last month (${prev_by_cat[cat]:,.0f}).",
        })
    elif by_cat:
        cat, amt = max(by_cat.items(), key=lambda kv: kv[1])
        share = amt / sum(by_cat.values()) * 100
        out.append({
            "tone": "neutral",
            "title": f"{cat} leads at {share:.0f}%",
            "body": f"${amt:,.0f} of your spending this month went to {cat.lower()}.",
        })

    if month["income"]:
        rate = (month["income"] - month["spent"]) / month["income"] * 100
        out.append({
            "tone": "pos" if rate >= 0 else "neg",
            "title": f"Saving {rate:.0f}% of income",
            "body": "Money in minus money out, as a share of what came in this month.",
        })
    return out[:3]


# --- Transactions ----------------------------------------------------------

@api.get("/transactions")
def list_transactions():
    q = Transaction.query
    if (kind := request.args.get("kind")) in ("income", "expense"):
        q = q.filter(Transaction.kind == kind)
    if category := request.args.get("category"):
        q = q.filter(Transaction.category == category)
    if month := request.args.get("month"):
        try:
            first, last = _month_bounds(datetime.strptime(month, "%Y-%m").date())
            q = q.filter(Transaction.occurred_on.between(first, last))
        except ValueError:
            raise BadRequest("Invalid month.")
    if text := request.args.get("q", "").strip():
        like = f"%{text}%"
        q = q.filter(or_(
            Transaction.note.ilike(like), Transaction.category.ilike(like), Transaction.raw_description.ilike(like),
        ))
    if source := request.args.get("source"):
        q = q.filter(Transaction.source == source)

    limit = min(request.args.get("limit", 1000, type=int), 5000)
    rows = q.order_by(Transaction.occurred_on.desc(), Transaction.id.desc()).limit(limit).all()
    income = sum((t.amount for t in rows if t.kind == "income"), Decimal(0))
    spent = sum((t.amount for t in rows if t.kind == "expense"), Decimal(0))

    months = {
        d.strftime("%Y-%m") for (d,) in
        db.session.query(Transaction.occurred_on).distinct()
    }
    return jsonify(
        transactions=[t.to_dict() for t in rows],
        income=float(income),
        spent=float(spent),
        months=sorted(months, reverse=True),
    )


@api.post("/transactions")
def create_transaction():
    data = request.get_json(silent=True) or {}
    kind, category = _kind_and_category(data)
    t = Transaction(
        kind=kind, amount=_amount(data.get("amount")),
        category=category, note=_note(data), occurred_on=_date(data.get("date")),
    )
    if data.get("repeat"):
        r = Recurring(
            kind=kind, amount=t.amount, category=category,
            note=t.note, day=t.occurred_on.day,
            next_date=add_month(t.occurred_on, t.occurred_on.day),
        )
        db.session.add(r)
        db.session.flush()
        t.recurring_id = r.id
        # Backfill if the first occurrence was more than a month ago
        db.session.add_all(r.post_due(date.today()))
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


def _own_transaction(txn_id):
    t = db.session.get(Transaction, txn_id)
    if not t:
        raise NotFound("Transaction not found.")
    return t


@api.patch("/transactions/<int:txn_id>")
def update_transaction(txn_id):
    t = _own_transaction(txn_id)
    data = request.get_json(silent=True) or {}
    old_category = t.category
    t.kind, t.category = _kind_and_category(data)
    t.amount = _amount(data.get("amount"))
    t.note = _note(data)
    t.occurred_on = _date(data.get("date"))
    learned = None
    # Recategorizing an imported transaction teaches Ledger about that merchant
    if t.raw_description and t.category != old_category:
        rule = importer.learn_rule(t.raw_description, t.kind, t.category)
        learned = rule.pattern if rule else None
    db.session.commit()
    return jsonify({**t.to_dict(), "learned": learned})


@api.delete("/transactions/<int:txn_id>")
def delete_transaction(txn_id):
    db.session.delete(_own_transaction(txn_id))
    db.session.commit()
    return jsonify(ok=True)


# --- Budgets ---------------------------------------------------------------

@api.get("/budgets")
def list_budgets():
    today = date.today()
    month_start, month_end = _month_bounds(today)
    three_months_ago = (month_start - timedelta(days=85)).replace(day=1)

    spend = defaultdict(lambda: {"month": Decimal(0), "history": Decimal(0)})
    rows = Transaction.query.filter(
        Transaction.kind == "expense",
        Transaction.occurred_on >= three_months_ago,
        Transaction.occurred_on <= today,
    )
    for t in rows:
        bucket = "month" if t.occurred_on >= month_start else "history"
        spend[t.category][bucket] += t.amount

    history_months = max(
        (month_start.year - three_months_ago.year) * 12 + month_start.month - three_months_ago.month, 1
    )
    budgets = {b.category: b.amount for b in Budget.query}
    fixed = _fixed_by_category()
    return jsonify(
        day=today.day,
        days=month_end.day,
        month=today.strftime("%B %Y"),
        categories=[
            {
                "name": c,
                "budget": _f(budgets.get(c)),
                "spent": float(spend[c]["month"]),
                "fixed": float(fixed.get(c, 0)),
                "average": float(spend[c]["history"] / history_months),
            }
            for c in EXPENSE_CATEGORIES
        ],
    )


@api.put("/budgets/<category>")
def set_budget(category):
    if category not in EXPENSE_CATEGORIES:
        raise BadRequest("Unknown category.")
    value = (request.get_json(silent=True) or {}).get("amount")
    budget = Budget.query.filter_by(category=category).first()
    if value in (None, "", 0, "0"):
        if budget:
            db.session.delete(budget)
    elif budget:
        budget.amount = _amount(value)
    else:
        db.session.add(Budget(category=category, amount=_amount(value)))
    db.session.commit()
    return jsonify(ok=True)


# --- Recurring -------------------------------------------------------------

@api.get("/recurring")
def list_recurring():
    items = Recurring.query.order_by(Recurring.active.desc(), Recurring.next_date).all()
    active = [r for r in items if r.active]
    income = sum((r.amount for r in active if r.kind == "income"), Decimal(0))
    fixed = sum((r.amount for r in active if r.kind == "expense"), Decimal(0))
    return jsonify(
        items=[r.to_dict() for r in items],
        income=float(income),
        fixed=float(fixed),
        fixed_share=_f(fixed / income * 100) if income else None,
    )


def _apply_recurring(r, data):
    r.kind, r.category = _kind_and_category(data)
    r.amount = _amount(data.get("amount"))
    r.note = _note(data)
    if not r.note:
        raise BadRequest("Give it a name, like \"Rent\" or \"Paycheck\".")
    r.next_date = _date(data.get("date"), allow_future=True)
    r.day = r.next_date.day
    if "active" in data:
        r.active = bool(data["active"])


@api.post("/recurring")
def create_recurring():
    r = Recurring(active=True)
    _apply_recurring(r, request.get_json(silent=True) or {})
    db.session.add(r)
    db.session.flush()
    db.session.add_all(r.post_due(date.today()))
    db.session.commit()
    return jsonify(r.to_dict()), 201


def _own_recurring(rid):
    r = db.session.get(Recurring, rid)
    if not r:
        raise NotFound("Recurring item not found.")
    return r


@api.patch("/recurring/<int:rid>")
def update_recurring(rid):
    r = _own_recurring(rid)
    data = request.get_json(silent=True) or {}
    if set(data) == {"active"}:
        r.active = bool(data["active"])
        # Resuming shouldn't backfill everything missed while paused
        today = date.today()
        while r.active and r.next_date < today:
            r.next_date = add_month(r.next_date, r.day)
    else:
        _apply_recurring(r, data)
        db.session.add_all(r.post_due(date.today()))
    db.session.commit()
    return jsonify(r.to_dict())


@api.delete("/recurring/<int:rid>")
def delete_recurring(rid):
    r = _own_recurring(rid)
    # Keep past transactions; just detach them
    Transaction.query.filter_by(recurring_id=r.id).update({"recurring_id": None})
    db.session.delete(r)
    db.session.commit()
    return jsonify(ok=True)


# --- Quick add ---------------------------------------------------------------

@api.get("/suggest")
def suggest():
    """Category guess for free text, used by quick add."""
    text = request.args.get("q", "")
    kind = request.args.get("kind", "expense")
    if kind not in ("income", "expense"):
        kind = "expense"
    return jsonify(importer.Categorizer().suggest(text, kind))


# --- Import ------------------------------------------------------------------

def _preview_csv(headers, rows, mapping):
    records = importer.apply_mapping(rows, mapping)
    return importer.build_preview(records)


@api.post("/import/parse")
def import_parse():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        raise BadRequest("Choose a CSV, OFX, or QFX file.")
    text = importer._decode(upload.read())
    try:
        if importer.is_ofx(text):
            items = importer.build_preview(importer.parse_ofx(text))
            return jsonify(format="ofx", filename=upload.filename, items=items)
        headers, rows = importer.read_csv(text)
    except ValueError as err:
        raise BadRequest(str(err))
    if not rows:
        raise BadRequest("No rows found under the header.")
    signature = importer.header_signature(headers)
    profile = ImportProfile.query.filter_by(signature=signature).first()
    mapping = profile.mapping if profile else importer.guess_mapping(headers, rows)
    return jsonify(
        format="csv",
        filename=upload.filename,
        headers=headers,
        rows=rows,
        signature=signature,
        profile=profile.name if profile else None,
        mapping=mapping,
        items=_preview_csv(headers, rows, mapping),
    )


@api.post("/import/preview")
def import_preview():
    data = request.get_json(silent=True) or {}
    headers, rows, mapping = data.get("headers") or [], data.get("rows") or [], data.get("mapping") or {}
    if mapping.get("date") is not None and not mapping.get("date_format"):
        mapping["date_format"] = importer.guess_date_format([r[mapping["date"]] for r in rows[:50]])
    return jsonify(mapping=mapping, items=_preview_csv(headers, rows, mapping))


@api.post("/import/commit")
def import_commit():
    data = request.get_json(silent=True) or {}
    items = [i for i in data.get("items") or [] if i.get("include")]
    if not items:
        raise BadRequest("Nothing selected to import.")
    storage.create_backup(datetime.now().strftime("%Y-%m-%d-%H%M%S") + "-before-import")
    imported, skipped, learned = importer.commit_items(items)
    if data.get("signature") and data.get("mapping"):
        profile = ImportProfile.query.filter_by(signature=data["signature"]).first()
        name = (data.get("profile") or data.get("filename") or "Bank CSV")[:80]
        if profile:
            profile.mapping, profile.last_used = data["mapping"], datetime.now()
        else:
            db.session.add(ImportProfile(signature=data["signature"], name=name, mapping=data["mapping"]))
    db.session.commit()
    return jsonify(imported=imported, skipped=skipped, learned=learned)


# --- Rules -------------------------------------------------------------------

@api.get("/rules")
def list_rules():
    rules = Rule.query.order_by(Rule.category, Rule.pattern).all()
    return jsonify(rules=[r.to_dict() for r in rules])


def _apply_rule(rule, data):
    pattern = str(data.get("pattern", "")).strip().lower()[:120]
    if len(pattern) < 2:
        raise BadRequest("The match text needs at least 2 characters.")
    clash = Rule.query.filter(Rule.pattern == pattern, Rule.id != (rule.id or 0)).first()
    if clash:
        raise BadRequest(f'There\'s already a rule for "{pattern}".')
    rule.pattern = pattern
    rule.kind, rule.category = _kind_and_category(data)
    rule.rename = str(data.get("rename") or "").strip()[:140] or None


@api.post("/rules")
def create_rule():
    rule = Rule()
    _apply_rule(rule, request.get_json(silent=True) or {})
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@api.patch("/rules/<int:rule_id>")
def update_rule(rule_id):
    rule = db.session.get(Rule, rule_id) or _not_found("Rule")
    _apply_rule(rule, request.get_json(silent=True) or {})
    db.session.commit()
    return jsonify(rule.to_dict())


@api.delete("/rules/<int:rule_id>")
def delete_rule(rule_id):
    db.session.delete(db.session.get(Rule, rule_id) or _not_found("Rule"))
    db.session.commit()
    return jsonify(ok=True)


@api.post("/rules/<int:rule_id>/apply")
def apply_rule_to_existing(rule_id):
    """Re-file past imported transactions that match this rule."""
    rule = db.session.get(Rule, rule_id) or _not_found("Rule")
    changed = 0
    for t in Transaction.query.filter(Transaction.raw_description.isnot(None), Transaction.kind == rule.kind):
        if rule.pattern in importer._haystack(t.raw_description) and t.category != rule.category:
            t.category = rule.category
            if rule.rename:
                t.note = rule.rename
            changed += 1
    rule.hits += changed
    db.session.commit()
    return jsonify(changed=changed)


def _not_found(what):
    raise NotFound(f"{what} not found.")


# --- Data: backups, sample data ----------------------------------------------

@api.get("/data")
def data_info():
    return jsonify(
        folder=str(DATA_DIR),
        db_size=DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        counts={
            "transactions": Transaction.query.count(),
            "imported": Transaction.query.filter_by(source="import").count(),
            "demo": Transaction.query.filter_by(source="demo").count(),
            "rules": Rule.query.count(),
            "recurring": Recurring.query.count(),
        },
        first_date=_iso(db.session.query(func.min(Transaction.occurred_on)).scalar()),
        backups=storage.list_backups(),
    )


def _iso(d):
    return d.isoformat() if d else None


@api.post("/backups")
def backup_now():
    path = storage.create_backup()
    return jsonify(name=path.name), 201


@api.get("/backups/<name>")
def download_backup(name):
    path = storage.backup_path(name) or _not_found("Backup")
    return send_file(path, as_attachment=True, download_name=path.name)


@api.post("/backups/<name>/restore")
def restore_backup(name):
    path = storage.backup_path(name) or _not_found("Backup")
    storage.restore_from(path)
    return jsonify(ok=True)


@api.post("/restore")
def restore_upload():
    upload = request.files.get("file")
    if not upload:
        raise BadRequest("Choose a Ledger backup file (.db).")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload.db"
        upload.save(path)
        if not storage.is_ledger_db(path):
            raise BadRequest("That isn't a Ledger backup file.")
        storage.restore_from(path)
    return jsonify(ok=True)


@api.post("/demo")
def load_demo():
    if Transaction.query.count() or Recurring.query.count():
        raise BadRequest("Sample data can only be loaded into an empty ledger.")
    demo.seed()
    return jsonify(ok=True), 201


@api.delete("/demo")
def remove_demo():
    Transaction.query.filter_by(source="demo").delete()
    Recurring.query.filter_by(source="demo").delete()
    Budget.query.filter_by(source="demo").delete()
    db.session.commit()
    return jsonify(ok=True)
