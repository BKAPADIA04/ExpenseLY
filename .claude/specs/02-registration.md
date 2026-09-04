# Spec: Registration

## Overview

Turn the existing `GET /register` stub into a working signup flow. The
`register.html` template already ships a complete POST form (`name`, `email`,
`password`) and an `{% if error %}` block, but `app.py` never handles the POST,
so submitting the form currently 405s. This step adds POST handling: validate
the submitted fields, reject duplicate emails, hash the password with werkzeug,
insert the user through a new helper in `database/db.py`, and redirect to the
login page on success. It is the first feature to write to the `users` table
created in Step 1, and it is the prerequisite for session-based login in Step 3
— every later feature (profile, expenses) needs real accounts to exist.

---

## Depends on

- **Step 1 — Database Setup** (complete): `get_db()`, `init_db()` and the
  `users` table with `email TEXT UNIQUE NOT NULL` and `password_hash TEXT NOT NULL`
  already exist and are called on app startup.

Nothing else. Session login and logout are **Step 3** and are explicitly out of
scope here.

---

## Routes

- `GET /register` — renders the empty signup form — **public** *(already exists;
  gains `methods=["GET", "POST"]`)*
- `POST /register` — validates input, creates the user, redirects to
  `GET /login` on success; re-renders `register.html` with an `error` message on
  failure — **public**

No other routes change. `/login` stays a GET-only stub — do **not** implement
its POST handler in this step.

---

## Database changes

**No database changes.** The `users` table from Step 1 already has every column
this feature needs (`name`, `email`, `password_hash`, `created_at` with its
`datetime('now')` default). Verified against `database/db.py`.

Two new **helper functions** are added to `database/db.py` (no schema change):

| Function | Purpose | Returns |
| --- | --- | --- |
| `get_user_by_email(email)` | Look up a single user by email (parameterised) | `sqlite3.Row` or `None` |
| `create_user(name, email, password_hash)` | Insert one user, commit, close | new user `id` (int) |

---

## Templates

- **Create:** None.
- **Modify:**
  - `templates/register.html`
    - Change `action="/register"` to `action="{{ url_for('register') }}"` —
      the hardcoded path violates the `url_for()` rule in CLAUDE.md.
    - Repopulate `name` and `email` inputs on a failed submit via
      `value="{{ name or '' }}"` / `value="{{ email or '' }}"` so the user does
      not retype them. Never repopulate the password field.
    - Keep the existing `{% if error %}<div class="auth-error">` block and all
      existing classes (`auth-card`, `form-group`, `form-input`, `btn-submit`)
      exactly as they are.

`templates/login.html` and `templates/base.html` are **not** touched. The navbar
stays non-session-aware until Step 3.

---

## Files to change

- `app.py`
  - Extend the flask import to `Flask, render_template, request, redirect, url_for`.
  - Import `create_user` and `get_user_by_email` from `database.db`.
  - Replace the `/register` route with a `methods=["GET", "POST"]` handler that
    delegates validation and DB work, then renders or redirects.
- `database/db.py`
  - Add `get_user_by_email(email)` and `create_user(name, email, password_hash)`.
  - `generate_password_hash` is already imported at the top of the file.
- `templates/register.html`
  - `url_for()` form action, sticky `name`/`email` values.

---

## Files to create

None.

---

## New dependencies

**No new dependencies.** `flask==3.1.3` and `werkzeug==3.1.6` are already in
`requirements.txt`; password hashing uses `werkzeug.security`, which
`database/db.py` already imports.

---

## Validation rules

Validate in this order and return the **first** failure as `error`:

| Field | Rule | Error message |
| --- | --- | --- |
| all | none may be empty | `All fields are required.` |
| `name` | 2–100 characters after stripping | `Please enter your full name.` |
| `email` | lowercased + stripped; must contain a single `@` with text either side and a `.` in the domain; max 120 chars | `Please enter a valid email address.` |
| `password` | minimum 8 characters (matches the form's "Min. 8 characters" placeholder) | `Password must be at least 8 characters.` |
| `email` | must not already exist in `users` | `An account with that email already exists.` |

Store the email **lowercased and stripped** so the `UNIQUE` constraint behaves
predictably.

**Whitespace handling:** strip `name` and `email` only. The password is **never**
stripped — trimming it would silently alter the user's credential and make the
account unloginnable in Step 3 unless login stripped identically forever. A
whitespace-only password counts as empty for the required-fields check, but the
length check and the hash both use the raw string.

**Ordering:** the required-fields check runs first, so an **empty** email yields
`All fields are required.`, not the email-format error. Only a non-empty,
malformed email produces `Please enter a valid email address.`

---

## Rules for implementation

- No SQLAlchemy or ORMs — `sqlite3` only
- Parameterised queries only — never f-strings or `%` formatting in SQL
- Passwords hashed with werkzeug (`generate_password_hash`) — never store or log
  the plaintext password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic inside route functions — every query lives in `database/db.py`
- Use `url_for()` for every internal link and form action
- The route function stays single-responsibility: read form → validate →
  call db helper → render or redirect
- Do **not** set `app.secret_key`, use `session`, or use `flash()` — those
  arrive with Step 3; success feedback is simply the redirect to `/login`
- Do **not** implement `POST /login`, `/logout`, or `/profile` in this step
- On validation failure, re-render `register.html` with `error` (do not redirect)
- Close every connection opened in `database/db.py` helpers

---

## Definition of done

- [ ] Submitting the register form with valid data creates a row in `users` and
      redirects to `/login`
- [ ] The stored `password_hash` is a werkzeug hash, not the plaintext password
- [ ] Registering with an email that already exists re-renders the form with
      "An account with that email already exists." and inserts nothing
- [ ] Submitting a password shorter than 8 characters shows the password error
      and inserts nothing
- [ ] Submitting a malformed email shows the email error, and submitting an empty
      email shows "All fields are required." — both insert nothing
- [ ] After a failed submit, the name and email fields are still filled in and
      the password field is empty
- [ ] `GET /register` still renders the form normally with no error box visible
- [ ] Emails are stored lowercased (`Test@X.com` and `test@x.com` collide)
- [ ] No SQL in `app.py` — all queries live in `database/db.py`
- [ ] The form's action renders through `url_for()`, not a hardcoded `/register`
- [ ] App starts on port 5001 with no errors and `/login`, `/logout`, `/profile`
      behave exactly as they did before this step
