# Allegderly: Cursor Build Prompt

## I. How you must work

You are helping me build **Allegderly**, an internal invoicing, inventory and returns/damages tracking web app. Follow this spec exactly.

- Work **one phase at a time**. Do not start the next phase until I say "continue".
- At the end of each phase: run `python manage.py check`, `python manage.py makemigrations --check`, and the tests. Then stop and give me (a) a short plain-English summary, (b) the list of files you created or changed, (c) anything you were unsure about.
- If something in this spec is ambiguous or conflicts with something else, **ask me**. Do not guess.
- Do not add features that are not in this spec. Do not add new dependencies without asking.
- I am a university CS student. Write simple, readable code with short comments explaining *why*, not *what*. I need to understand every part of it.
- I am on **Windows with PowerShell**. Give terminal commands in PowerShell syntax.
- The GitHub repo is **https://github.com/BilalDotExe/Allegerly.git**. The active branch is **dev**. After I confirm a phase is accepted, push that phase's work to `dev`. Never push to `main` unless I explicitly say so.

## II. Project summary

- A single-business internal tool for my family business. We manufacture soap bars (in batches) plus sell other items.
- Replaces QuickBooks for us, because QuickBooks has no good flow for returns, damaged goods and expired items.
- A handful of staff users. No public sign-up. **USD only.**
- Developed on Windows now. Later hosted on a Raspberry Pi (Raspberry Pi OS, gunicorn, Nginx, HTTPS, WireGuard VPN for remote access). Everything must stay portable between Windows and Linux.

## III. Fixed tech stack

- Python 3.12, Django (keep the version already installed in the venv, do not upgrade), SQLite.
- Installed packages: `django`, `django-axes`, `python-dotenv`, `pillow`.
- Frontend: Django templates + **Bootstrap 5 vendored locally** in `static/` (no CDN, so it works on a LAN with no internet). HTMX is allowed, also vendored locally. **No React, Vue or Node build step.**
- Config comes from `.env` via python-dotenv.

## IV. Current state (already done, do not redo)

- Project `allegderly` created in the current folder with `venv`, VS Code.
- Apps created: `customers`, `inventory`, `invoices`, `damages`, `returns`, `production`, `reports`, `audit`.
- `settings.py` is written (env-based config, django-axes, secure cookies tied to DEBUG). `.env` exists with `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`. `templates/` and `static/` folders exist.
- Models already written and migrated:
  - `customers.Customer` (name, email, phone, address, created_at, plus balance methods)
  - `inventory.Item` (sku, name, description, cost_price, sale_price, reorder_level, has_expiry, created_at)
  - `inventory.StockMovement` (item, movement_type, quantity signed, note, created_by, created_at)
  - `invoices.Invoice`, `InvoiceLine`, `Payment`, `CreditNote`
- Read the existing code first before changing anything.

## V. Business rules (these must be enforced in code, not just in the UI)

1. **Stock is never a stored number.** On-hand stock = sum of `StockMovement.quantity`. Movements are append-only: never edited, never deleted.
2. **Issued invoices are immutable.** No editing customer, lines or prices after issuing. Mistakes are fixed by voiding. Voiding creates reversing stock movements, it never deletes anything.
3. **Money** uses `DecimalField`, rounded to 2 places (ROUND_HALF_UP). Never floats.
4. **Sale price is copied onto the invoice line** so later price changes do not alter old invoices.
5. **Cannot sell more than on-hand stock.** Stock must never go negative.
6. **Return vs damage, never both for the same unit.** For each invoice line: `returned_qty + damaged_qty <= line quantity`. A unit is either returned or damaged, never both.
7. **Damaged goods:**
   - Standalone report: item, quantity, date, note, and an **optional** link to an invoice (for reference only, not enforced).
   - Always deducts from stock via a negative `damaged` StockMovement.
   - Records a financial loss at the item's `cost_price` (hits expenses, not sales).
   - No automatic credit note. If a replacement is needed, staff manually creates a new $0 invoice with a note referencing the damage report number.
   - The optional invoice link is for traceability only and does not affect any calculations.
8. **Returns (normal customer return):**
   - Linked to an invoice line. Creates a credit note for the returned quantity at the line's unit price.
   - If marked restockable (default yes), adds stock back with a `return` StockMovement.
   - Credit note can be applied to a future invoice of the same customer (partial application allowed, tracked in a `CreditApplication` model).
9. **Expired items:** internal only.
   - Logged as an `ExpiryWriteOff` (item, quantity, date noticed, note).
   - Creates a negative `expired` StockMovement. Cannot exceed on-hand stock.
   - Records a financial loss at the item's `cost_price`.
   - No customer involved, no credit note.
10. **Batches exist at production level only.** A `ProductionBatch` records item, quantity produced, production date, expiry date (optional), auto batch code. Creating one adds stock via a `production` StockMovement. Sales, returns and damages are NOT linked to batches (our boxes carry no batch labels).
11. **Payments** cannot be deleted. A wrong payment is voided by an admin with a reason. Payments cannot exceed the invoice balance. Invoice status moves to `paid` automatically when balance reaches zero.
12. **Customer balances** are always calculated from records, never typed in:
    - Billed = issued + paid invoices (NOT draft, NOT voided)
    - Outstanding = billed - payments - credits applied
    - Credit balance = credit notes not yet fully applied
13. Every important action writes to the **audit log** in the same database transaction as the action.
14. Customers and items with history cannot be deleted. Use an `is_active` flag instead.

## VI. Phases

### Phase 1: Groundwork (start here)

- `git init`, a proper `.gitignore` (venv, `.env`, `db.sqlite3`, `__pycache__`, `*.pyc`, `backups/`, `staticfiles/`, `media/`, `logs/`).
- Add the remote: `git remote add origin https://github.com/BilalDotExe/Allegerly.git`
- Check out the `dev` branch: `git checkout -b dev` (create it if it does not exist locally yet).
- Do all work on `dev`. Do not touch `main`.
- At the end of Phase 1, after I confirm it is accepted, commit everything with a clear message (e.g. `feat: phase 1 groundwork`) and push: `git push -u origin dev`. Do not push before I confirm.
- Create `.env.example` with placeholder values, and `requirements.txt` (pinned versions).
- **Fix known problems in `settings.py`:**
  - Remove `SECURE_BROWSER_XSS_FILTER` (removed in Django 4.0, does nothing).
  - Add `SESSION_SAVE_EVERY_REQUEST = True` so the 1-hour timeout is an *inactivity* timeout, not absolute.
  - Fail loudly if `SECRET_KEY` is missing or empty. Strip empty entries when parsing `ALLOWED_HOSTS`.
  - Add `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`.
  - Add a block that only applies when `DEBUG` is False: `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER` (for Nginx), HSTS (controlled by an env variable so I can enable it only after HTTPS is confirmed working), `STATIC_ROOT`.
  - Add rotating-file logging to a `logs/` folder (git-ignored).
  - Check the installed django-axes version and make sure the axes settings match its current API.
- Create a `core` app for shared utilities: base template, dashboard view, permission helpers, money rounding helper.
- Vendor Bootstrap 5 into `static/`. Build `templates/base.html` (navbar, flash messages, responsive), login and logout pages, and a placeholder dashboard.
- Create **three permission groups** via a data migration: `Admin`, `Staff`, `ViewOnly`.
  - Admin: everything, including voiding invoices or payments, manual stock adjustments, viewing the audit log.
  - Staff: create invoices, record payments, log damage reports, returns, expiry write-offs, production batches. Cannot void or do manual stock adjustments.
  - ViewOnly: read-only on all pages.
- Every view must require login and check the correct group permission. No exceptions.

### Phase 2: Fix and complete the core models

- **Customer:** add `is_active`. Rewrite balance methods using database aggregation (`Sum`), not Python loops. Fix `total_billed` so it includes both `issued` and `paid` status invoices (the current version misses `paid`, which is a bug).
- **Invoice:** auto-generated sequential `invoice_number` (e.g. `INV-000001`), generated safely inside a `transaction.atomic`. Optional invoice-level `tax_percent` (default 0). Enforce status transition rules and block field edits once status is `issued`.
- **InvoiceLine:** remove `has_return` and `has_damage` boolean fields. Replace with computed properties that sum quantities from linked returns and damage reports.
- **Payment:** add `is_voided`, `void_reason`, `voided_by`.
- **CreditNote:** add `credit_number`. Link to its source return record (one-to-one). Default `remaining_amount` to `amount` on creation. Add `CreditApplication` model to track partial applications. Add refund fields: `is_refunded`, `refund_method`, `refund_date`.
- **StockMovement:** make append-only by overriding `save()` to block updates and overriding `delete()` to raise an error. Validate that the quantity sign matches the movement type (e.g. `sale` must be negative, `purchase` must be positive). Add a nullable generic foreign key to record what caused this movement (invoice, damage report, expiry write-off, etc.).
- Put all business operations in each app's `services.py` (e.g. `issue_invoice()`, `void_invoice()`, `record_payment()`), each wrapped in `transaction.atomic`. Views call services and stay thin.
- Create new migrations. Do not edit migrations that were already applied. If a clean reset of `db.sqlite3` and migration files would be cleaner (no real data yet), **ask me first**.

### Phase 3: Damages, returns, expiry

- `damages.DamageReport` model and service:
  - Fields: item (FK to Item), quantity, date_reported, note, optional invoice (FK to Invoice, null/blank, for reference only), created_by.
  - Service creates a negative `damaged` StockMovement and records the loss value (quantity x item.cost_price). No credit note.
  - Enforce that damaged quantity does not push total damage + returns for that invoice line over the line quantity (only when an invoice is linked).
- `returns.ReturnRecord` model and service:
  - Fields: invoice_line (FK to InvoiceLine), quantity, date_returned, is_restockable (default True), note, created_by.
  - Service creates a credit note, and if restockable, a positive `return` StockMovement.
  - Enforce rule 6: returned_qty + damaged_qty <= line quantity.
- `inventory.ExpiryWriteOff` model and service:
  - Fields: item (FK to Item), quantity, date_noticed, note, created_by.
  - Service creates a negative `expired` StockMovement and records the loss value (quantity x item.cost_price). Cannot exceed on-hand stock.
- Manual stock adjustment service (Admin only): item, quantity (signed), reason (required). Creates an `adjustment` StockMovement.

### Phase 4: Production

- `production.ProductionBatch` model and service:
  - Fields: item (FK to Item), quantity_produced, production_date, expiry_date (optional), batch_code (auto-generated, e.g. `BATCH-000001`), note, created_by.
  - Service creates a positive `production` StockMovement.
- Dashboard alert: show all batches with an expiry date within N days (N from settings, default 30). Informational only: batch code, item, quantity produced, expiry date.

### Phase 5: Audit trail

- `audit.AuditLog`: user (FK), action (string), timestamp, object_type, object_id, object_repr, changes (JSONField, stores old and new values), ip_address.
- **Append-only:** override `save()` to block updates on existing rows. Override `delete()` to raise an error. In Django admin, make it fully read-only with no delete action available.
- Single helper function `audit.services.log(user, action, obj, changes, request)` called from the services layer, inside the same `transaction.atomic`.
- Log logins, failed logins, and axes lockout events using Django signals.
- Admin-only audit log page: filterable by user, action, date range, object type. Paginated.

### Phase 6: User interface

Bootstrap 5, mobile-friendly, pagination and search on all list views. Pages needed:

- Dashboard: low stock alerts, outstanding invoices count, recent damage reports, expiry alerts for production batches.
- Customers: list, create, edit, detail page (shows billed, paid, outstanding balance, credit balance, full invoice history).
- Items: list, create, edit, detail page (shows current stock, full stock movement history).
- Invoices: list with filters (status, customer, date range), create with dynamic line item rows (Django formset or HTMX), detail view, issue action, void action, record payment, **print view** with a dedicated print stylesheet (no navbar, clean layout).
- Credit notes: list, detail, apply to invoice, mark as refunded.
- Damage report form (item, quantity, date, note, optional invoice link).
- Return form (select invoice line, quantity, restockable toggle, note).
- Expiry write-off form.
- Production batch form.
- Stock movements list (read-only, filterable by item and type).
- Manual stock adjustment form (Admin only).
- Audit log page (Admin only).

### Phase 7: Reports

All reports have a date range filter and a **CSV export** button:

- Sales by period (total invoiced, total paid, outstanding)
- Outstanding invoices with ageing buckets (0-30 days, 31-60 days, 61+ days)
- Stock levels and low stock items
- Damaged goods summary (by item, total quantity, total loss at cost)
- Returns summary (by item, by customer, credit notes issued)
- Expiry write-offs summary (by item, total quantity, total loss at cost)
- Production summary (by item, batches produced, quantities, expiry dates)

### Phase 8: Tests and security review

- Unit tests for every business rule in section V (focus on rules 2, 5, 6, 7, 8, 9, 11, 12).
- User permissions
- Permission tests: ViewOnly cannot POST anywhere, Staff cannot void or adjust stock, Admin can do everything.
- Run `python manage.py check --deploy` with `DEBUG=False` and resolve every issue it reports.
- Audit every view: login required, correct permission checked, CSRF present, no raw SQL with string formatting, all input goes through Django forms.
- Write a short security notes file listing anything you think is still a weak point.

### Phase 9: Raspberry Pi preparation (files and docs only, do NOT run any deployment commands)

- `gunicorn.conf.py` configured for production.
- Sample Nginx config: HTTPS on 443, proxy to gunicorn, security headers (HSTS, X-Frame-Options, CSP basic).
- Sample systemd service file for gunicorn.
- A `backup_db` Django management command using SQLite's built-in backup API (works on both Windows and Linux), writing timestamped copies to a `backups/` folder.
- `DEPLOY.md` with step-by-step Pi instructions: create a non-root user, SSH key authentication only (disable password login), disable root SSH, UFW firewall rules, system updates, obtain a certificate (self-signed for LAN or Let's Encrypt if domain is used), enable HSTS only after HTTPS is confirmed, WireGuard VPN setup for remote access, cron job for db backup.

## VII. Security requirements (apply throughout every phase)

- Use Django's built-in auth system. Never write custom password handling or session logic.
- Validate all input server-side with Django forms or model validation. Never trust the browser.
- ORM only. Never concatenate user input into raw SQL strings.
- Never use `@csrf_exempt`. Never disable or remove any middleware from the current list.
- No secrets in source code. `.env` is always git-ignored.
- Passwords validated by all four of Django's built-in password validators.
- Login attempt limiting via django-axes with the settings already in place.
- `DEBUG=False` and a specific `ALLOWED_HOSTS` in production.
- Least privilege enforced on every view via the three permission groups.

## VIII. Do NOT include

- Online payments, payment gateways, card processing of any kind
- REST API or Django REST Framework
- React, Vue, Node.js, or any JavaScript build tooling
- Docker, cloud hosting, multi-tenant or multi-company support
- Multi-currency (USD only throughout)
- Public user registration, password-reset emails, or any outbound email
- Vendors, purchase orders, bills, expenses, chart of accounts, payroll, estimates, bank feeds, tax filing
- Batch tracking on sales, returns or damages (production batches exist but are not linked to individual sales)
- Deletion of any transactional record: invoices, payments, credit notes, stock movements, damage reports, return records, expiry write-offs, audit logs. Use voiding or write-offs instead.
- Windows-only file paths, libraries or commands
- Any new pip package without asking me first

## IX. Definition of done (each phase)

- `python manage.py check` shows 0 issues (0 warnings, 0 errors).
- `python manage.py makemigrations --check` shows no pending changes.
- All tests pass with no errors or failures.
- Code is readable, with comments explaining *why* a decision was made where it is not obvious.
- You have stopped, reported back, and are waiting for me to say "continue".
- Once I confirm the phase is accepted, commit with a descriptive message and push to `dev`. Never push before I confirm.

**Start with Phase 1 only.**
