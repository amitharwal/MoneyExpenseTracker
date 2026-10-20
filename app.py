import csv
import hmac
import io
import secrets
from datetime import date

from flask import Flask, abort, redirect, render_template, request, session, url_for

import storage
from api import api
from config import DATA_DIR, EXPENSE_CATEGORIES, INCOME_CATEGORIES, Config
from models import Transaction, db


def _secret_key():
    """A random key generated on first run and kept in the data folder."""
    path = DATA_DIR / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48))
        path.chmod(0o600)
    return path.read_text().strip()


app = Flask(__name__)
app.config.from_object(Config)
app.config["SECRET_KEY"] = _secret_key()
db.init_app(app)
app.register_blueprint(api)

with app.app_context():
    storage.init_db()

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


# --- Local-only safety --------------------------------------------------------

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def guard():
    # Reject requests addressed to any other hostname (DNS-rebinding protection)
    if request.host.rsplit(":", 1)[0] not in ALLOWED_HOSTS:
        abort(403)
    # Websites you visit can't make changes here: writes need this page's token
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.headers.get("X-CSRF-Token") or request.form.get("_csrf", "")
        if not hmac.compare_digest(session.get("_csrf", ""), sent):
            abort(400, "Invalid CSRF token. Reload the page and try again.")


# --- Pages ------------------------------------------------------------------

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        expense_categories=EXPENSE_CATEGORIES,
        income_categories=INCOME_CATEGORIES,
        today=date.today().isoformat(),
    )


@app.route("/login")
@app.route("/register")
def old_auth_pages():
    return redirect(url_for("dashboard"))


@app.get("/export.csv")
def export_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Type", "Category", "Description", "Amount", "Bank description", "Source"])
    for t in Transaction.query.order_by(Transaction.occurred_on.desc()):
        writer.writerow([
            t.occurred_on.isoformat(), t.kind, t.category, t.note,
            f"{t.signed:.2f}", t.raw_description or "", t.source,
        ])
    return out.getvalue(), 200, {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": f"attachment; filename=ledger-{date.today().isoformat()}.csv",
    }


if __name__ == "__main__":
    from run import main
    main()
