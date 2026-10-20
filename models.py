import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc)


def add_month(d: date, day: int) -> date:
    """The same day-of-month next month, clamped to the month's length."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(7), nullable=False)  # "income" | "expense"
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # always positive
    category = db.Column(db.String(32), nullable=False, index=True)
    note = db.Column(db.String(140), nullable=False, default="")
    occurred_on = db.Column(db.Date, nullable=False, index=True)
    recurring_id = db.Column(db.Integer, db.ForeignKey("recurring.id", ondelete="SET NULL"))
    # Where it came from: manual | import | recurring | demo
    source = db.Column(db.String(10), nullable=False, default="manual", index=True)
    # Imported rows keep the bank's text and a fingerprint so re-imports skip them
    raw_description = db.Column(db.String(255))
    import_hash = db.Column(db.String(64), unique=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    @property
    def signed(self) -> Decimal:
        return self.amount if self.kind == "income" else -self.amount

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "amount": float(self.amount),
            "category": self.category,
            "note": self.note,
            "date": self.occurred_on.isoformat(),
            "recurring": self.recurring_id is not None,
            "source": self.source,
            "raw": self.raw_description,
        }


class Budget(db.Model):
    """A monthly spending limit for one expense category."""
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(32), nullable=False, unique=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    source = db.Column(db.String(10), nullable=False, default="manual")


class Recurring(db.Model):
    """A monthly bill or paycheck that is logged automatically when due."""
    __tablename__ = "recurring"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    note = db.Column(db.String(140), nullable=False, default="")
    day = db.Column(db.Integer, nullable=False)  # day of month, 1–31
    next_date = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    source = db.Column(db.String(10), nullable=False, default="manual")

    def post_due(self, today: date) -> list:
        """Create transactions for every occurrence on or before today."""
        posted = []
        while self.active and self.next_date <= today:
            posted.append(Transaction(
                kind=self.kind, amount=self.amount, category=self.category, note=self.note,
                occurred_on=self.next_date, recurring_id=self.id,
                source="demo" if self.source == "demo" else "recurring",
            ))
            self.next_date = add_month(self.next_date, self.day)
        return posted

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "amount": float(self.amount),
            "category": self.category,
            "note": self.note,
            "day": self.day,
            "next_date": self.next_date.isoformat(),
            "active": self.active,
        }


class Rule(db.Model):
    """'If the bank description contains X, file it under Y.' Learned from your edits."""
    __tablename__ = "rules"

    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(120), nullable=False, unique=True)  # lowercase
    kind = db.Column(db.String(7), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    rename = db.Column(db.String(140))  # optional friendly name to use as the note
    hits = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    def to_dict(self):
        return {
            "id": self.id, "pattern": self.pattern, "kind": self.kind,
            "category": self.category, "rename": self.rename, "hits": self.hits,
        }


class ImportProfile(db.Model):
    """Remembers how a bank's CSV columns map, keyed by its header row."""
    __tablename__ = "import_profiles"

    id = db.Column(db.Integer, primary_key=True)
    signature = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(80), nullable=False)
    mapping = db.Column(db.JSON, nullable=False)
    last_used = db.Column(db.DateTime(timezone=True), default=_now)
