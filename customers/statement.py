"""Customer statement: every invoice, payment and credit application for one
customer, in date order, with a running balance. Used by both the CSV export
and the printable statement — one source of the numbers for both."""
from dataclasses import dataclass, field
from datetime import date

from core.money import money, zero_money
from invoices.models import CreditApplication, Invoice, Payment


@dataclass
class StatementRow:
    date: date
    description: str
    reference: str
    debit: "object" = None   # Decimal or None — charged to the customer
    credit: "object" = None  # Decimal or None — paid/credited by the customer
    balance: "object" = field(default_factory=zero_money)


def build_statement(customer):
    """Returns (rows, opening_balance, closing_balance). Voided invoices and
    voided payments are left out — they never affected what the customer owes."""
    entries = []  # (date, sort_rank, description, reference, debit, credit)

    invoices = Invoice.objects.filter(customer=customer, status__in=("issued", "paid")).order_by()
    for inv in invoices:
        entries.append((inv.issue_date, 0, f"Invoice {inv.invoice_number}", inv.invoice_number, inv.total, None))

    payments = Payment.objects.filter(invoice__customer=customer, is_voided=False).select_related("invoice")
    for pay in payments:
        entries.append((
            pay.payment_date, 1, f"Payment — {pay.get_method_display()} ({pay.invoice.invoice_number})",
            pay.invoice.invoice_number, None, pay.amount,
        ))

    credits = CreditApplication.objects.filter(invoice__customer=customer).select_related(
        "credit_note", "invoice"
    )
    for app in credits:
        entries.append((
            app.created_at.date(), 1,
            f"Credit {app.credit_note.credit_number} applied ({app.invoice.invoice_number})",
            app.invoice.invoice_number, None, app.amount,
        ))

    entries.sort(key=lambda e: (e[0] or date.min, e[1]))

    rows = []
    running = zero_money()
    for entry_date, _rank, description, reference, debit, credit in entries:
        running = money(running + (debit or 0) - (credit or 0))
        rows.append(StatementRow(
            date=entry_date, description=description, reference=reference,
            debit=debit, credit=credit, balance=running,
        ))

    closing_balance = running
    return rows, closing_balance
