from flask import Flask, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from database.db import (
    EmailAlreadyExistsError,
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
)

app = Flask(__name__)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 120
PASSWORD_MIN_LENGTH = 8

DUPLICATE_EMAIL_ERROR = "An account with that email already exists."


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


@app.route("/login")
def login():
    return render_template("login.html")


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
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
