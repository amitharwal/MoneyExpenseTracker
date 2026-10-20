import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """Where the database and backups live. Override with LEDGER_DATA_DIR."""
    if override := os.environ.get("LEDGER_DATA_DIR"):
        path = Path(override).expanduser()
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Ledger"
    elif os.name == "nt":
        path = Path(os.environ.get("APPDATA", Path.home())) / "Ledger"
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ledger"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = data_dir()
DB_PATH = DATA_DIR / "ledger.db"
BACKUP_DIR = DATA_DIR / "backups"
BACKUPS_TO_KEEP = 30

HOST = "127.0.0.1"
PORT = int(os.environ.get("LEDGER_PORT", 5001))


class Config:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # statement files and backup restores


EXPENSE_CATEGORIES = [
    "Housing", "Groceries", "Dining", "Transport", "Bills",
    "Shopping", "Entertainment", "Health", "Travel", "Other",
]
INCOME_CATEGORIES = ["Salary", "Freelance", "Investments", "Gifts", "Other"]

# Starter keywords used when no learned rule matches. Matched against the
# lowercased, cleaned description; first hit wins, so keep specific ones first.
DEFAULT_KEYWORDS = [
    ("expense", "Groceries", ["trader joe", "whole foods", "safeway", "kroger", "aldi", "costco", "wegmans", "publix", "sprouts", "grocery", "market"]),
    ("expense", "Dining", ["restaurant", "cafe", "coffee", "starbucks", "chipotle", "sweetgreen", "mcdonald", "doordash", "uber eats", "grubhub", "pizza", "taco", "burger", "sushi", "ramen", "bar ", "grill", "kitchen", "bakery", "blue bottle", "dunkin", "panera", "chick-fil-a"]),
    ("expense", "Transport", ["uber", "lyft", "shell", "chevron", "exxon", "bp ", "gas", "fuel", "parking", "transit", "metro", "mta", "bart", "clipper", "toll"]),
    ("expense", "Bills", ["comcast", "xfinity", "verizon", "at&t", "t-mobile", "pg&e", "electric", "water", "utility", "insurance", "geico", "progressive", "internet", "phone"]),
    ("expense", "Housing", ["rent", "mortgage", "hoa", "property management", "apartments"]),
    ("expense", "Entertainment", ["netflix", "spotify", "hulu", "disney", "hbo", "max.com", "youtube", "apple music", "steam", "playstation", "xbox", "nintendo", "cinema", "theater", "amc", "ticketmaster", "concert"]),
    ("expense", "Shopping", ["amazon", "amzn", "target", "walmart", "best buy", "apple.com", "apple store", "ikea", "uniqlo", "nike", "etsy", "ebay", "home depot", "lowe"]),
    ("expense", "Health", ["pharmacy", "cvs", "walgreens", "rite aid", "doctor", "dental", "dentist", "clinic", "hospital", "medical", "gym", "fitness", "equinox", "planet fitness"]),
    ("expense", "Travel", ["airline", "airlines", "delta", "united", "southwest", "jetblue", "american air", "airbnb", "hotel", "marriott", "hilton", "hyatt", "expedia", "booking.com"]),
    ("income", "Salary", ["payroll", "direct dep", "salary", "paycheck", "adp", "gusto"]),
    ("income", "Investments", ["dividend", "interest paid", "interest payment", "brokerage"]),
    ("income", "Freelance", ["invoice", "stripe", "paypal transfer", "upwork", "fiverr"]),
]
