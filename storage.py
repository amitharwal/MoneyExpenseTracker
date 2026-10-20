"""Database file housekeeping: SQLite tuning, schema top-ups, backups, legacy import."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine

from config import BACKUP_DIR, BACKUPS_TO_KEEP, DB_PATH
from models import db

LEGACY_DB = Path(__file__).parent / "instance" / "expenses.db"


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")  # readers never block the writer
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def init_db():
    db.create_all()
    _add_missing_columns()
    _import_legacy()
    ensure_daily_backup()


def _add_missing_columns():
    """create_all() won't alter existing tables, so add any new columns ourselves."""
    insp = inspect(db.engine)
    with db.engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(db.engine.dialect)}'
                if col.default is not None and col.default.is_scalar:
                    ddl += f" DEFAULT {_sql_literal(col.default.arg)}"
                conn.execute(text(ddl))


def _sql_literal(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


# --- Backups ---------------------------------------------------------------

def _copy_sqlite(src: Path, dest: Path):
    """Consistent copy of a live SQLite file using the backup API."""
    with sqlite3.connect(src) as s, sqlite3.connect(dest) as d:
        s.backup(d)


def create_backup(label: str | None = None) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = label or datetime.now().strftime("%Y-%m-%d-%H%M%S")
    dest = BACKUP_DIR / f"ledger-{stamp}.db"
    _copy_sqlite(DB_PATH, dest)
    _prune()
    return dest


def ensure_daily_backup():
    if DB_PATH.exists() and not (BACKUP_DIR / f"ledger-{date.today().isoformat()}.db").exists():
        create_backup(date.today().isoformat())


def _prune():
    files = sorted(BACKUP_DIR.glob("ledger-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[BACKUPS_TO_KEEP:]:
        old.unlink()


def list_backups():
    if not BACKUP_DIR.exists():
        return []
    files = sorted(BACKUP_DIR.glob("ledger-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {"name": p.name, "size": p.stat().st_size,
         "created": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")}
        for p in files
    ]


def backup_path(name: str) -> Path | None:
    path = BACKUP_DIR / Path(name).name
    return path if path.exists() and path.suffix == ".db" else None


def is_ledger_db(path: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return "transactions" in tables
    except sqlite3.DatabaseError:
        return False


def restore_from(path: Path):
    """Replace the live database with `path`, keeping a safety backup first."""
    create_backup(datetime.now().strftime("%Y-%m-%d-%H%M%S") + "-before-restore")
    db.session.remove()
    db.engine.dispose()
    _copy_sqlite(path, DB_PATH)
    init_db()


# --- One-time import from the old multi-user database ----------------------

def _import_legacy():
    """Carry over data from instance/expenses.db (the old login-based app) once.
    The legacy file is only ever read, never modified or deleted."""
    if not LEGACY_DB.exists() or db.session.execute(text("SELECT COUNT(*) FROM transactions")).scalar():
        return
    old = None
    try:
        old = sqlite3.connect(f"file:{LEGACY_DB}?mode=ro", uri=True)
        old.row_factory = sqlite3.Row
        tables = {r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "transactions" not in tables:
            return
        first_user = old.execute("SELECT MIN(user_id) FROM transactions").fetchone()[0]
        if first_user is None:
            return
        id_map = {}
        if "recurring" in tables:
            for r in old.execute("SELECT * FROM recurring WHERE user_id=?", (first_user,)):
                res = db.session.execute(text(
                    "INSERT INTO recurring (kind, amount, category, note, day, next_date, active, source) "
                    "VALUES (:kind, :amount, :category, :note, :day, :next_date, :active, 'manual')"
                ), dict(r))
                id_map[r["id"]] = res.lastrowid
        for t in old.execute("SELECT * FROM transactions WHERE user_id=?", (first_user,)):
            row = dict(t)
            row["recurring_id"] = id_map.get(row.get("recurring_id"))
            db.session.execute(text(
                "INSERT INTO transactions (kind, amount, category, note, occurred_on, recurring_id, source) "
                "VALUES (:kind, :amount, :category, :note, :occurred_on, :recurring_id, 'manual')"
            ), row)
        if "budgets" in tables:
            for b in old.execute("SELECT category, amount FROM budgets WHERE user_id=?", (first_user,)):
                db.session.execute(text(
                    "INSERT OR IGNORE INTO budgets (category, amount, source) VALUES (:category, :amount, 'manual')"
                ), dict(b))
        db.session.commit()
    finally:
        if old is not None:
            old.close()
