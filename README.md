# Allegderly

An internal business management web app built for a small soap manufacturing and retail operation. Handles invoicing, inventory, purchasing, returns, damages, and financial reporting — all running offline on a local network with no internet dependency.

Built with Python / Django + SQLite. Designed to run on a Raspberry Pi over a LAN.

---

## Table of Contents

- [Features Overview](#features-overview)
- [Tech Stack](#tech-stack)
- [Setup](#setup)
- [User Roles](#user-roles)
- [Invoices](#invoices)
- [Customers](#customers)
- [Purchase Orders](#purchase-orders)
- [Vendors](#vendors)
- [Inventory](#inventory)
- [Production Batches](#production-batches)
- [Returns](#returns)
- [Damage Reports](#damage-reports)
- [Credit Notes](#credit-notes)
- [Reports & Insights](#reports--insights)
- [Audit Log](#audit-log)
- [Deployment (Raspberry Pi)](#deployment-raspberry-pi)

---

## Features Overview

- Full invoicing workflow: draft → issue → payment → paid
- Customer statements and balance tracking
- Purchase order management with goods receiving
- Append-only stock ledger (no stored stock number — always calculated from movements)
- Damage report tracking with optional credit note issuance
- Customer returns with restocking and credit note support
- Expiry write-offs for perishable items
- Production batch logging for manufactured goods
- CSV export on all list and report pages
- Role-based access control (Admin / Staff / ViewOnly / Employee)
- Full audit log of every important action
- Offline-ready: no CDN, no external fonts, no JS build step

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 6.1.1 |
| Database | SQLite |
| Frontend | Django templates, Bootstrap 5 (vendored) |
| Auth protection | django-axes (brute-force lockout) |
| Deployment | Gunicorn + Nginx on Raspberry Pi OS |
| Remote access | WireGuard VPN |

---

## Setup

**Requirements:** Python 3.12, pip

```bash
# 1. Clone the repo
git clone https://github.com/BilalDotExe/Allegerly.git
cd Allegerly

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux / macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file (copy the example and fill it in)
copy .env.example .env       # Windows
cp .env.example .env         # Linux

# 5. Run migrations
python manage.py migrate

# 6. Create a superuser (first admin account)
python manage.py createsuperuser

# 7. Start the development server
python manage.py runserver
```

Open `http://127.0.0.1:8000` in your browser and log in.

### .env variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key — generate a long random string |
| `DEBUG` | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames/IPs |
| `TIME_ZONE` | e.g. `America/New_York` |

---

## User Roles

Access is controlled by four permission groups assigned in the Django admin.

| Group | What they can do |
|---|---|
| **Admin** | Full access — void invoices, void payments, manual stock adjustments, audit log, employee management, company settings |
| **Staff** | Create and issue invoices, record payments, log damage reports, returns, expiry write-offs, production batches. Cannot void or adjust stock manually |
| **ViewOnly** | Read-only access to all pages |
| **Employee** | Simplified view — invoices only, no customers, no inventory management |

A superuser account bypasses all group checks and has full access including the Django admin panel at `/admin/`.

---

## Invoices

**Path:** Sales → Invoices

Invoices move through a fixed status lifecycle:

```
Draft → Issued → Paid
              ↘ Voided
```

- **Draft** invoices can be edited freely. Lines, customer, prices — all editable. Draft invoices can also be **deleted** permanently (Admin only).
- **Issuing** an invoice locks it, deducts stock for each line, and makes it eligible for payments.
- **Payments** are recorded against an issued invoice. The invoice moves to **Paid** automatically when the balance reaches zero.
- **Voiding** an issued invoice reverses all stock movements and marks all payments as voided. The invoice number is never reused.
- Issued and paid invoices have a **Print view** formatted for printing or saving as PDF.
- Wholesale customers cannot have tax applied to their invoices.
- Each invoice line copies the sale price at the time of issue — future price changes do not affect historical invoices.

---

## Customers

**Path:** Sales → Customers

- Stores name, contact details, address, and customer type (retail / wholesale).
- The customer **detail page** shows their full invoice history, outstanding balance, credit balance, and all payments received.
- **Receive payment** on the customer page records a payment against a specific open invoice.
- **Statements** can be generated for any date range and printed or exported as CSV.
- Customers with invoice history cannot be deleted — they are deactivated instead.

---

## Purchase Orders

**Path:** Purchasing → Purchase Orders

Purchase orders track goods ordered from vendors.

```
Draft → Placed → Partially Received → Received
              ↘ Cancelled
```

- A **draft PO** records what you intend to order (vendor, lines, expected delivery).
- **Placing** the order marks it as sent to the vendor.
- **Receiving goods** records how many units actually arrived and at what buying price. Partial deliveries are supported — the PO stays open until fully received.
- Receiving goods automatically creates positive stock movements for each line.
- POs can be printed for record-keeping.

---

## Vendors

**Path:** Purchasing → Vendors

Stores supplier information linked to purchase orders. Vendors with purchase history cannot be deleted.

---

## Inventory

**Path:** Inventory → Items / Stock Movements / Stock Adjustment

### Items

Each item has a SKU, name, cost price, sale price, and reorder level. Items with any stock history cannot be deleted — they are deactivated.

### Stock Movements

Stock is never stored as a single number. The on-hand quantity for any item is always calculated as the sum of all its `StockMovement` records. Movement types:

| Type | Created by |
|---|---|
| `purchase` | Receiving goods on a PO |
| `sale` | Issuing an invoice |
| `return` | Recording a restockable customer return |
| `production` | Logging a production batch |
| `damaged` | Manual stock adjustment linked to a damage report |
| `expired` | Logging an expiry write-off |
| `adjustment` | Manual stock adjustment (Admin only) |
| `void_sale` | Voiding an issued invoice |
| `void_return` | Voiding a return |

Movements are append-only — never edited or deleted.

### Stock Adjustment

Admins can create manual stock adjustments with a reason note. If an adjustment is to reconcile a damage report, the adjustment can be linked to a specific damage report from the adjustment page — the damage report then shows as reconciled.

### Expiry Write-offs

Items flagged as having expiry dates can be written off when they expire. Each write-off records the item, quantity, date noticed, and a note. It creates a negative `expired` stock movement.

---

## Production Batches

**Path:** Inventory → Production Batches

Records manufactured goods. Each batch logs:
- Item produced
- Quantity
- Production date
- Optional expiry date
- Auto-generated batch code

Creating a batch adds stock via a `production` movement. Sales and returns are not linked to specific batches.

---

## Returns

**Path:** Sales → Returns

Records a customer returning items from a specific invoice line.

- Linked to an invoice line — only lines from issued or paid invoices can be returned.
- Quantity cannot exceed the remaining unreturned/undamaged quantity on that line.
- **Restockable** (default): adds a `return` stock movement, putting the units back in inventory.
- **Non-restockable**: no stock movement; the goods are written off.
- Always creates a **credit note** for `quantity × unit price` from the original invoice line.
- Credit resolution options:
  - **Apply as credit** — credit note balance can be applied against a future invoice
  - **Refund directly** — immediately marks as refunded with a payment method

---

## Damage Reports

**Path:** Reports → Damage Reports

Records goods that were damaged (in transit, in storage, etc.).

- A damage report is a **pure record** — it does not automatically touch stock.
- Optionally linked to an invoice line for traceability (e.g. items damaged during delivery of a specific sale).
- If the customer is owed compensation for damaged goods, check **"Issue a credit note"** when filing the report — this follows the same credit note workflow as returns.
- To adjust stock after confirming a loss, click **Adjust stock** on the damage report list. This opens the stock adjustment page pre-filled with the damage details. Once the adjustment is saved, the report shows as reconciled.

---

## Credit Notes

**Path:** Reports → Credit Notes

Credit notes are created automatically by the Returns and Damage Reports modules. They can also be applied manually.

- Each credit note has a **remaining balance** that can be partially or fully applied.
- **Apply to invoice**: deducts the credit amount from an open invoice of the same customer.
- **Mark as refunded**: records that the credit was paid back directly (cash, bank transfer, etc.).
- Credit notes cannot exceed the original invoice line amount.

---

## Reports & Insights

**Path:** Insights → Reports

All reports support date range filtering and CSV export.

| Report | What it shows |
|---|---|
| Sales | All issued/paid invoices with totals |
| Outstanding | Customers with an unpaid balance |
| Stock Levels | Current on-hand quantity for all items |
| Damage Reports | All damage records with linked credit notes |
| Returns | All return records |
| Expiry Write-offs | All expired item write-offs |
| Production | All production batches |

---

## Audit Log

**Path:** Insights → Audit Log (Admin only)

Every important action in the app writes a timestamped audit entry in the same database transaction. This includes creating/voiding invoices, recording payments, adjusting stock, logging damages, and all user account changes. The audit log is read-only and cannot be edited or deleted.

---

## Deployment (Raspberry Pi)

The app is designed to run on a Raspberry Pi on a local network, accessible to staff devices over Wi-Fi. For remote access, a WireGuard VPN tunnel is used.

**Production stack:** Gunicorn (WSGI server) + Nginx (reverse proxy) + SQLite

Key settings for production (set in `.env`):

```
DEBUG=False
ALLOWED_HOSTS=<your Pi's LAN IP>,<your VPN IP>
SECRET_KEY=<long random string>
```

Static files are served by Nginx directly. Run `python manage.py collectstatic` after any update.

Database backups: SQLite is a single file (`db.sqlite3`). Schedule a cron job to copy it to a USB drive or network share regularly.
