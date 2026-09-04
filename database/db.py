import sqlite3
from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    if existing["count"] > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    today = date.today()
    year, month = today.year, today.month

    def d(day):
        return date(year, month, day).isoformat()

    sample_expenses = [
        (user_id, 45.50, "Food",          d(2),  "Groceries"),
        (user_id, 12.00, "Transport",     d(4),  "Bus pass top-up"),
        (user_id, 89.99, "Bills",         d(5),  "Electricity bill"),
        (user_id, 25.00, "Health",        d(9),  "Pharmacy"),
        (user_id, 15.75, "Entertainment", d(12), "Movie tickets"),
        (user_id, 60.20, "Shopping",      d(18), "New shoes"),
        (user_id, 9.99,  "Other",         d(21), "Misc purchase"),
        (user_id, 32.40, "Food",          d(27), "Restaurant dinner"),
    ]

    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        sample_expenses,
    )

    conn.commit()
    conn.close()


class EmailAlreadyExistsError(Exception):
    """Raised when a users row with the same email already exists."""


def get_user_by_email(email):
    """Return the users row matching email, or None.

    The email is expected already stripped and lowercased by the caller.
    """
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return user


def create_user(name, email, password_hash):
    """Insert one user and return its new id.

    Raises EmailAlreadyExistsError if the UNIQUE email constraint fires.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        raise EmailAlreadyExistsError(email) from exc
    finally:
        conn.close()
