from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    EmailAlreadyExistsError,
    create_user,
    get_db,
    get_expenses_for_user,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 120
PASSWORD_MIN_LENGTH = 8

DUPLICATE_EMAIL_ERROR = "An account with that email already exists."
INVALID_LOGIN_ERROR = "Invalid email or password."


def is_valid_email(email):
    """A single @ with text either side, and a dot somewhere in the domain."""
    if len(email) > EMAIL_MAX_LENGTH or email.count("@") != 1:
        return False
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain


def validate_registration(name, email, password):
    """Return the first validation error message, or None if input is valid.

    The name and email are expected pre-stripped (email also lowercased).
    The password is never stripped — only checked.
    """
    if not name or not email or not password.strip():
        return "All fields are required."

    if not NAME_MIN_LENGTH <= len(name) <= NAME_MAX_LENGTH:
        return "Please enter your full name."

    if not is_valid_email(email):
        return "Please enter a valid email address."

    if len(password) < PASSWORD_MIN_LENGTH:
        return "Password must be at least 8 characters."

    return None


DATE_FORMAT = "%Y-%m-%d"


def parse_filter_date(value):
    """Return value unchanged if it's a valid YYYY-MM-DD string, else None."""
    if not value:
        return None
    try:
        datetime.strptime(value, DATE_FORMAT)
        return value
    except ValueError:
        return None


def format_currency(amount):
    return f"${amount:,.2f}"


def format_display_date(iso_date):
    dt = datetime.strptime(iso_date, DATE_FORMAT)
    return f"{dt.strftime('%b')} {dt.day}"


def initials_from_name(name):
    return "".join(part[0] for part in name.split()[:2]).upper()


def format_member_since(created_at):
    dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%B %Y")


def build_profile_context(expenses):
    """Turn a list of expense rows into (stats, transactions, categories)
    context for profile.html."""
    transactions = [
        {
            "date": format_display_date(e["date"]),
            "description": e["description"] or "—",
            "category": e["category"],
            "amount": format_currency(e["amount"]),
        }
        for e in expenses
    ]

    category_totals = {}
    for e in expenses:
        category_totals[e["category"]] = (
            category_totals.get(e["category"], 0) + e["amount"]
        )

    total_spent = sum(category_totals.values())
    top_category = max(category_totals, key=category_totals.get) if category_totals else "—"

    stats = [
        {"label": "Total spent", "value": format_currency(total_spent)},
        {"label": "Transactions", "value": str(len(expenses))},
        {"label": "Top category", "value": top_category},
    ]

    categories = [
        {"category": category, "amount": format_currency(amount)}
        for category, amount in sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        )
    ]

    return stats, transactions, categories


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = validate_registration(name, email, password)
    if error is None and get_user_by_email(email) is not None:
        error = DUPLICATE_EMAIL_ERROR

    if error is None:
        try:
            create_user(name, email, generate_password_hash(password))
            return redirect(url_for("login"))
        except EmailAlreadyExistsError:
            error = DUPLICATE_EMAIL_ERROR

    return render_template("register.html", error=error, name=name, email=email)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error=INVALID_LOGIN_ERROR)

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    raw_start_date = request.args.get("start_date", "")
    raw_end_date = request.args.get("end_date", "")
    start_date = parse_filter_date(raw_start_date)
    end_date = parse_filter_date(raw_end_date)

    start_is_malformed = bool(raw_start_date) and start_date is None
    end_is_malformed = bool(raw_end_date) and end_date is None
    backwards_range = bool(start_date) and bool(end_date) and start_date > end_date
    if start_is_malformed or end_is_malformed or backwards_range:
        start_date = end_date = None

    user_row = get_user_by_id(session["user_id"])
    expenses = get_expenses_for_user(session["user_id"], start_date, end_date)
    stats, transactions, categories = build_profile_context(expenses)

    return render_template(
        "profile.html",
        user={
            "name": user_row["name"],
            "email": user_row["email"],
            "initials": initials_from_name(user_row["name"]),
            "member_since": format_member_since(user_row["created_at"]),
        },
        stats=stats,
        transactions=transactions,
        categories=categories,
        start_date=start_date or "",
        end_date=end_date or "",
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
