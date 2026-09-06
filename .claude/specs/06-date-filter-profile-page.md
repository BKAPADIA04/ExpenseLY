# Spec: Date Filter on Profile Page

## Overview
The profile page (Step 4) currently renders entirely hardcoded data —
`PROFILE_USER`, `PROFILE_STATS`, `PROFILE_TRANSACTIONS`, and
`PROFILE_CATEGORY_BREAKDOWN` in `app.py`. There is no Step 5 in the roadmap
that wires `/profile` to the real `users`/`expenses` tables, so a date filter
has nothing real to filter yet. This step folds that missing backend
connection into the same feature: `/profile` starts querying real data for
the logged-in user via new `database/db.py` helpers, and a date-range filter
(`start_date` / `end_date` query params) is layered on top so the user info
card, summary stats, transaction table, and category breakdown all reflect
either all-time data or a selected date range. This is the first feature to
read from the `expenses` table.

## Depends on
- **Step 1 — Database Setup** (complete): `expenses` table with `user_id`,
  `amount`, `category`, `date` (`YYYY-MM-DD`), `description`.
- **Step 2 — Registration** (complete): real user accounts exist in `users`.
- **Step 3 — Login/Logout** (complete, no spec file): `session["user_id"]`
  and `session["user_name"]` are set on login; `/profile` is already guarded.
- **Step 4 — Profile Page** (complete): `templates/profile.html` layout
  (user card, stat row, transaction table, category list) already exists and
  is reused as-is — only its data source and a filter bar are added.

## Routes
- `GET /profile` — **modified** (no new route). Now accepts two optional
  query params, `start_date` and `end_date` (`YYYY-MM-DD`, from an
  `<input type="date">`). Renders real data for `session["user_id"]`, scoped
  to the date range when both/either param is present and valid — logged-in
  only (unchanged auth guard, redirects to `/login`).

If no new routes beyond this modification: confirmed — no other routes change.

## Database changes
No schema changes. `users` and `expenses` already have every column needed.

New **helper functions** added to `database/db.py`:

| Function | Purpose | Returns |
| --- | --- | --- |
| `get_user_by_id(user_id)` | Look up a single user by id (parameterised) | `sqlite3.Row` or `None` |
| `get_expenses_for_user(user_id, start_date=None, end_date=None)` | Fetch a user's expenses, optionally scoped to an inclusive date range, newest first | list of `sqlite3.Row` |

`get_expenses_for_user` builds its `WHERE` clause conditionally
(`user_id = ?`, then `AND date >= ?` / `AND date <= ?` only when a bound is
given) — every value is still passed as a `?` parameter, never interpolated.

## Templates
- **Create:** None.
- **Modify:**
  - `templates/profile.html`
    - Add a filter bar above the stat row: a `GET` form
      (`action="{{ url_for('profile') }}"`) with two `<input type="date">`
      fields (`name="start_date"`, `name="end_date"`), sticky-populated from
      `{{ start_date or '' }}` / `{{ end_date or '' }}`, an "Apply" submit
      button, and a "Clear" link back to `{{ url_for('profile') }}`.
    - Add an empty-state row/message ("No transactions in this date range.")
      shown when `transactions` is empty.
    - No other structural changes — existing blocks (user card, stat row,
      transaction table, category list) keep their current markup/classes.

## Files to change
- `app.py`
  - Import `get_user_by_id` and `get_expenses_for_user` from `database.db`;
    drop the `PROFILE_USER` / `PROFILE_STATS` / `PROFILE_TRANSACTIONS` /
    `PROFILE_CATEGORY_BREAKDOWN` hardcoded constants (Step 4 leftovers).
  - Add private (non-route) helpers: date-string validation, currency
    formatting (`$1,234.56`), display-date formatting (ISO → `"Jan 27"`),
    initials-from-name, and stats/category aggregation from a list of
    expense rows. These are plain data shaping, not SQL, so they stay in
    `app.py`.
  - Rewrite the `/profile` route: read + validate `start_date`/`end_date`
    from `request.args` (invalid format or `start_date > end_date` ⇒ treat
    both as unset rather than erroring), fetch the user and their expenses
    via the new db helpers, build the stats/transactions/categories context
    with the formatting helpers, and render `profile.html`.
- `database/db.py` — add `get_user_by_id` and `get_expenses_for_user`.
- `templates/profile.html` — filter bar markup, sticky values, empty state.

## Files to create
- `static/css/profile.css` — styles for the new filter bar (date inputs,
  apply/clear controls) and the empty-state row, linked from
  `templates/profile.html` via the `{% block head %}` slot in `base.html`.
  Page-specific styles do not belong in the shared `style.css`.

## New dependencies
No new dependencies. Date parsing uses `datetime.strptime` from the standard
library (already imported in `database/db.py`; import it in `app.py` too).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — conditional `WHERE` clauses are fine, but
  every value is bound with `?`, never f-string/`%`-interpolated
- Passwords hashed with werkzeug (unchanged — no auth code touched here)
- Use CSS variables — never hardcode hex values in `profile.css`
- All templates extend `base.html`
- No DB logic inside route functions — `get_user_by_id` and
  `get_expenses_for_user` are the only places SQL runs
- Use `url_for()` for the filter form's `action` and the "Clear" link
- An invalid or backwards date range degrades to "no filter" (all-time),
  it must never raise a 500
- Stats, transaction table, and category breakdown must all be derived from
  the same filtered expense list — no double-querying with mismatched ranges

## Definition of done
- [ ] Visiting `/profile` without being logged in still redirects to `/login`
- [ ] Visiting `/profile` while logged in shows the real logged-in user's
      name/email/member-since (from `users`), not the old `PROFILE_USER` stub
- [ ] With no query params, the page shows all of that user's expenses,
      matching what existed in the `expenses` table before this change
- [ ] Submitting the filter form with a valid `start_date`/`end_date` narrows
      the transaction table, the "Total spent"/"Transactions"/"Top category"
      stats, and the category breakdown to only expenses in that inclusive
      range
- [ ] Reloading the filtered URL directly (e.g. bookmarked
      `/profile?start_date=2025-01-01&end_date=2025-01-15`) reproduces the
      same filtered view — the filter state lives in the query string
- [ ] The date inputs retain the submitted values after filtering (sticky)
- [ ] A date range matching zero expenses shows the empty-state message
      instead of an empty table with no explanation
- [ ] An end date before the start date, or a malformed date string typed
      directly into the URL, falls back to the unfiltered (all-time) view
      instead of erroring
- [ ] Clicking "Clear" returns to the unfiltered `/profile` view
- [ ] No hex colour values appear in `profile.css` — only CSS variables
- [ ] No SQL appears in `app.py` — only in `database/db.py`
- [ ] App starts on port 5001 with no errors; `/login`, `/logout`,
      `/register` behave exactly as before this step
