"""
Tests for Step 6 — Date Filter + real backend connection on the Profile page.

Spec: .claude/specs/06-date-filter-profile-page.md

These tests are written against the spec's stated behavior only:
- GET /profile is auth-guarded (redirects to /login when logged out).
- With no query params, /profile shows the logged-in user's real data from
  the `users`/`expenses` tables (no more PROFILE_* stub constants).
- Optional `start_date`/`end_date` query params (YYYY-MM-DD, inclusive range)
  narrow the transaction table, the "Total spent" / "Transactions" /
  "Top category" stats, and the category breakdown consistently.
- The filtered view is fully reproducible from the query string (bookmarkable
  / reloadable), and the date inputs are sticky.
- A valid range matching zero expenses shows an explicit empty-state message.
- An invalid range (end before start, or a malformed date string) silently
  falls back to the unfiltered, all-time view instead of erroring.
- A "Clear" link/affordance returns to the unfiltered `/profile` view.

Because `database/db.py`'s `get_db()` always connects to a fixed on-disk
`DB_PATH` (there is no Flask `app.config['DATABASE']` hook), test isolation
is achieved by monkeypatching `database.db.DB_PATH` to a fresh temp-file
path per test, then using the app's own `init_db()` / `create_user()` /
registration+login flow to populate it. Expense rows are inserted directly
via `database.db.get_db()` with parameterized SQL, since no expense-creation
route/helper exists yet (Step 7 is still a stub).
"""

import re

import pytest

import database.db as db
from app import app as flask_app


# --------------------------------------------------------------------- #
# Fixtures                                                               #
# --------------------------------------------------------------------- #


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app wired to a fresh, isolated SQLite file per test."""
    db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    flask_app.config.update({"TESTING": True})
    db.init_db()

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, name="Test User", email="testuser@example.com", password="password123"):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=False,
    )


def login(client, email="testuser@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


@pytest.fixture
def registered_user(client):
    """Registers a user and returns (email, password, user_id)."""
    email = "testuser@example.com"
    password = "password123"
    register(client, email=email, password=password)
    user_row = db.get_user_by_email(email)
    assert user_row is not None, "Registration should have created a users row"
    return {"email": email, "password": password, "user_id": user_row["id"]}


@pytest.fixture
def auth_client(client, registered_user):
    """A test client that is logged in as `registered_user`."""
    login(client, email=registered_user["email"], password=registered_user["password"])
    return client


def insert_expense(user_id, amount, category, date_str, description=None):
    """Directly insert one expense row using the real db connection.

    Bypasses the (not-yet-implemented) add-expense route while still going
    through database.db.get_db() and parameterized SQL, per project rules.
    """
    conn = db.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date_str, description),
    )
    conn.commit()
    conn.close()


def count_all_expenses():
    conn = db.get_db()
    row = conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()
    conn.close()
    return row["n"]


def extract_input_value(html, name):
    """Find `<input ... name="{name}" ...>` and return its value attribute
    (or '' if the tag has no value attribute), regardless of attribute
    order. Returns None if no such input tag is found."""
    tag_match = re.search(rf'<input\b[^>]*\bname="{re.escape(name)}"[^>]*>', html)
    if tag_match is None:
        return None
    tag = tag_match.group(0)
    value_match = re.search(r'\bvalue="([^"]*)"', tag)
    return value_match.group(1) if value_match else ""


EMPTY_STATE_MESSAGE = b"No transactions in this date range."


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #


class TestProfileAuthGuard:
    def test_profile_logged_out_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Logged-out /profile should redirect, not render"
        assert response.headers["Location"].endswith("/login"), (
            f"Expected redirect to /login, got {response.headers['Location']!r}"
        )

    def test_profile_logged_out_with_filter_params_still_redirects(self, client):
        response = client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login"), (
            "Query params must not bypass the auth guard"
        )


# --------------------------------------------------------------------- #
# Real data (no hardcoded stub), no filter applied                      #
# --------------------------------------------------------------------- #


class TestProfileRealDataNoFilter:
    def test_profile_shows_logged_in_users_real_name_and_email(self, auth_client, registered_user):
        response = auth_client.get("/profile")
        assert response.status_code == 200
        body = response.data.decode()
        assert registered_user["email"] in body, "Real user email should be rendered"
        assert "Test User" in body, "Real user name should be rendered"

    def test_profile_no_filter_shows_all_of_users_expenses(self, auth_client, registered_user):
        insert_expense(registered_user["user_id"], 20.00, "Food", "2024-01-10", "Groceries")
        insert_expense(registered_user["user_id"], 45.00, "Transport", "2024-01-20", "Bus pass")
        insert_expense(registered_user["user_id"], 12.34, "Bills", "2023-12-25", "Electric bill")

        response = auth_client.get("/profile")
        body = response.data.decode()

        assert response.status_code == 200
        assert "Groceries" in body
        assert "Bus pass" in body
        assert "Electric bill" in body

    def test_profile_does_not_show_another_users_expenses(self, client):
        register(client, name="User One", email="user1@example.com", password="password123")
        user1 = db.get_user_by_email("user1@example.com")
        register(client, name="User Two", email="user2@example.com", password="password123")
        user2 = db.get_user_by_email("user2@example.com")

        insert_expense(user1["id"], 15.00, "Food", "2024-01-05", "UserOneLunch")
        insert_expense(user2["id"], 999.00, "Shopping", "2024-01-05", "UserTwoSpree")

        login(client, email="user1@example.com", password="password123")
        response = client.get("/profile")
        body = response.data.decode()

        assert "UserOneLunch" in body
        assert "UserTwoSpree" not in body, "A user must never see another user's expenses"

    def test_profile_get_requests_do_not_mutate_the_database(self, auth_client, registered_user):
        insert_expense(registered_user["user_id"], 20.00, "Food", "2024-01-10", "Groceries")
        before = count_all_expenses()

        auth_client.get("/profile")
        auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")

        after = count_all_expenses()
        assert after == before, "Viewing /profile must not create/modify/delete expense rows"


# --------------------------------------------------------------------- #
# Filtering behavior                                                     #
# --------------------------------------------------------------------- #


@pytest.fixture
def seeded_expenses(registered_user):
    """A fixed set of expenses spanning multiple months/categories, used to
    exercise range filtering."""
    uid = registered_user["user_id"]
    insert_expense(uid, 20.00, "Food", "2024-01-10", "FilteredGroceries")
    insert_expense(uid, 45.00, "Transport", "2024-01-20", "FilteredBusPass")
    insert_expense(uid, 999.00, "Entertainment", "2024-02-15", "MovieNight")
    insert_expense(uid, 12.34, "Bills", "2023-12-25", "ElectricBillDec")
    return uid


class TestProfileDateFiltering:
    def test_valid_range_narrows_transaction_table(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        body = response.data.decode()

        assert response.status_code == 200
        assert "FilteredGroceries" in body
        assert "FilteredBusPass" in body
        assert "MovieNight" not in body, "Expense after the range must be excluded"
        assert "ElectricBillDec" not in body, "Expense before the range must be excluded"

    def test_valid_range_narrows_stats_consistently(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        body = response.data.decode()

        # Total spent = 20.00 + 45.00 = 65.00; formatted per spec as "$X,XXX.XX"
        assert "$65.00" in body, "Total spent stat should reflect only the filtered expenses"
        # Top category by spend within the range is Transport (45.00 > 20.00)
        assert "Transport" in body
        # Excluded expense's amount must not leak into the total
        assert "$999.00" not in body and "$1,064.34" not in body, (
            "Total spent must not include expenses outside the filtered range"
        )

    def test_valid_range_narrows_category_breakdown(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        body = response.data.decode()

        assert "Food" in body
        assert "Transport" in body
        assert "Bills" not in body, "Category outside the filtered range must not appear"
        assert "Entertainment" not in body, "Category outside the filtered range must not appear"

    def test_open_ended_start_date_only_filters_from_that_date_onward(
        self, auth_client, seeded_expenses
    ):
        response = auth_client.get("/profile?start_date=2024-01-01")
        body = response.data.decode()

        assert "FilteredGroceries" in body
        assert "FilteredBusPass" in body
        assert "MovieNight" in body
        assert "ElectricBillDec" not in body, "Expense before start_date must be excluded"

    def test_open_ended_end_date_only_filters_up_to_that_date(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile?end_date=2024-01-31")
        body = response.data.decode()

        assert "FilteredGroceries" in body
        assert "FilteredBusPass" in body
        assert "ElectricBillDec" in body
        assert "MovieNight" not in body, "Expense after end_date must be excluded"

    def test_range_boundaries_are_inclusive(self, auth_client, registered_user):
        uid = registered_user["user_id"]
        insert_expense(uid, 5.00, "Food", "2024-01-01", "OnStartBoundary")
        insert_expense(uid, 6.00, "Food", "2024-01-31", "OnEndBoundary")
        insert_expense(uid, 7.00, "Food", "2023-12-31", "JustBeforeStart")
        insert_expense(uid, 8.00, "Food", "2024-02-01", "JustAfterEnd")

        response = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        body = response.data.decode()

        assert "OnStartBoundary" in body
        assert "OnEndBoundary" in body
        assert "JustBeforeStart" not in body
        assert "JustAfterEnd" not in body


# --------------------------------------------------------------------- #
# Reload reproducibility + sticky inputs                                 #
# --------------------------------------------------------------------- #


class TestProfileFilterUrlAndStickyInputs:
    def test_filtered_url_is_reproducible_on_direct_reload(self, auth_client, seeded_expenses):
        url = "/profile?start_date=2024-01-01&end_date=2024-01-31"

        first = auth_client.get(url)
        second = auth_client.get(url)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.data == second.data, (
            "Reloading a bookmarked filtered URL must reproduce the same view"
        )

    def test_date_inputs_are_sticky_after_filtering(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        body = response.data.decode()

        start_value = extract_input_value(body, "start_date")
        end_value = extract_input_value(body, "end_date")

        assert start_value == "2024-01-01", "start_date input should retain the submitted value"
        assert end_value == "2024-01-31", "end_date input should retain the submitted value"

    def test_date_inputs_are_empty_when_no_filter_applied(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile")
        body = response.data.decode()

        start_value = extract_input_value(body, "start_date")
        end_value = extract_input_value(body, "end_date")

        assert start_value in ("", None)
        assert end_value in ("", None)


# --------------------------------------------------------------------- #
# Empty-state                                                            #
# --------------------------------------------------------------------- #


class TestProfileEmptyState:
    def test_valid_range_matching_zero_expenses_shows_empty_state_message(
        self, auth_client, seeded_expenses
    ):
        response = auth_client.get("/profile?start_date=2030-01-01&end_date=2030-01-31")
        body = response.data

        assert response.status_code == 200
        assert EMPTY_STATE_MESSAGE in body, (
            "An explicit empty-state message must be shown, not a silently empty table"
        )
        assert b"FilteredGroceries" not in body
        assert b"MovieNight" not in body

    def test_empty_state_not_shown_when_there_are_matching_expenses(
        self, auth_client, seeded_expenses
    ):
        response = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        assert EMPTY_STATE_MESSAGE not in response.data


# --------------------------------------------------------------------- #
# Invalid ranges fall back to all-time, never 500                       #
# --------------------------------------------------------------------- #


class TestProfileInvalidRangeFallback:
    def test_end_date_before_start_date_falls_back_to_all_time(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile?start_date=2024-02-01&end_date=2024-01-01")

        assert response.status_code == 200, "A backwards range must never raise a 500"
        body = response.data.decode()
        # All four seeded expenses should be visible — the filter was ignored.
        assert "FilteredGroceries" in body
        assert "FilteredBusPass" in body
        assert "MovieNight" in body
        assert "ElectricBillDec" in body

    @pytest.mark.parametrize(
        "start_date, end_date",
        [
            ("not-a-date", ""),
            ("2024-13-40", "2024-01-31"),
            ("2024/01/01", "2024/01/31"),
            ("", "banana"),
        ],
    )
    def test_malformed_date_strings_fall_back_to_all_time(
        self, auth_client, seeded_expenses, start_date, end_date
    ):
        response = auth_client.get(f"/profile?start_date={start_date}&end_date={end_date}")

        assert response.status_code == 200, "A malformed date string must never raise a 500"
        body = response.data.decode()
        assert "FilteredGroceries" in body
        assert "FilteredBusPass" in body
        assert "MovieNight" in body
        assert "ElectricBillDec" in body

    def test_one_malformed_bound_falls_back_to_all_time_even_if_other_is_valid(
        self, auth_client, seeded_expenses
    ):
        response = auth_client.get("/profile?start_date=2024-01-01&end_date=not-a-date")

        assert response.status_code == 200
        body = response.data.decode()
        assert "MovieNight" in body, "A malformed bound should not silently apply the valid one"
        assert "ElectricBillDec" in body


# --------------------------------------------------------------------- #
# Clear affordance                                                       #
# --------------------------------------------------------------------- #


class TestProfileClearFilter:
    def test_clear_link_points_back_to_unfiltered_profile(self, auth_client, seeded_expenses):
        response = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        body = response.data.decode()

        assert re.search(r'href="/profile"', body), (
            "A 'Clear' link back to the unfiltered /profile view should be present"
        )

    def test_navigating_to_unfiltered_profile_shows_all_expenses_again(
        self, auth_client, seeded_expenses
    ):
        filtered = auth_client.get("/profile?start_date=2024-01-01&end_date=2024-01-31")
        assert b"MovieNight" not in filtered.data

        cleared = auth_client.get("/profile")
        body = cleared.data.decode()
        assert "FilteredGroceries" in body
        assert "FilteredBusPass" in body
        assert "MovieNight" in body
        assert "ElectricBillDec" in body
