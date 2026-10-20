"""Sample data so a new account has something to look at."""
import random
from datetime import date, timedelta
from decimal import Decimal

from models import Budget, Recurring, Transaction, db

RECURRING = [
    ("income", 2150, "Salary", "Paycheck", 1),
    ("income", 2150, "Salary", "Paycheck", 15),
    ("expense", 1650, "Housing", "Rent", 1),
    ("expense", 65, "Bills", "Internet", 12),
    ("expense", 42, "Bills", "Phone", 20),
    ("expense", 15.49, "Entertainment", "Netflix", 9),
    ("expense", 11.99, "Entertainment", "Spotify", 9),
    ("expense", 38, "Health", "Gym membership", 3),
]

BUDGETS = {
    "Groceries": 520, "Dining": 380, "Transport": 160, "Shopping": 250,
    "Entertainment": 60, "Bills": 260, "Health": 90,
}

VARIABLE = [
    # probability per day, category, (low, high), merchants
    (1 / 7, "Groceries", (55, 150), ["Trader Joe's", "Whole Foods", "Safeway"]),
    (0.42, "Dining", (8, 46), ["Sweetgreen", "Chipotle", "Blue Bottle", "Thai Basil", "Pizza night", "Ramen Shop"]),
    (0.22, "Transport", (3, 30), ["Uber", "Transit", "Gas station"]),
    (0.07, "Shopping", (20, 180), ["Amazon", "Uniqlo", "Target", "Apple"]),
    (0.03, "Health", (15, 90), ["Pharmacy", "Dentist copay"]),
    (0.03, "Travel", (80, 420), ["Flight", "Airbnb", "Hotel"]),
    (0.04, "Entertainment", (12, 70), ["Movies", "Concert", "Bowling"]),
]


def seed(today=None):
    """Everything created here is tagged source="demo" so it can be removed in one click."""
    today = today or date.today()
    rng = random.Random(42)
    start = today - timedelta(days=182)
    first_of_start = start.replace(day=1)

    db.session.add(Transaction(
        kind="income", amount=Decimal("3800.00"), category="Other", note="Opening balance",
        occurred_on=first_of_start - timedelta(days=1), source="demo",
    ))

    for kind, amount, category, note, day in RECURRING:
        r = Recurring(
            kind=kind, amount=Decimal(str(amount)), category=category, note=note, day=day,
            next_date=first_of_start.replace(day=day), active=True, source="demo",
        )
        db.session.add(r)
        db.session.flush()
        db.session.add_all(r.post_due(today))

    d = first_of_start
    while d <= today:
        for chance, category, (low, high), merchants in VARIABLE:
            if rng.random() < chance:
                db.session.add(Transaction(
                    kind="expense", amount=Decimal(str(round(rng.uniform(low, high), 2))),
                    category=category, note=rng.choice(merchants), occurred_on=d, source="demo",
                ))
        if rng.random() < 0.035:
            db.session.add(Transaction(
                kind="income", amount=Decimal(str(round(rng.uniform(200, 850), 2))),
                category="Freelance", note="Client invoice", occurred_on=d, source="demo",
            ))
        d += timedelta(days=1)

    for category, amount in BUDGETS.items():
        db.session.add(Budget(category=category, amount=Decimal(amount), source="demo"))

    db.session.commit()
