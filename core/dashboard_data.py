"""Aggregations behind the dashboard charts. A handful of queries, no per-row N+1."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.charts import (
    column_chart, delta, fmt_money, month_key, month_starts, rank_bars, segments, sparkline,
)
from core.money import money
from damages.models import DamageReport
from inventory.models import ExpiryWriteOff, Item
from invoices.models import (
    _LINE_TOTAL, CreditApplication, CreditNote, Invoice, InvoiceLine, Payment,
)
from purchasing.models import PurchaseOrder
from returns.models import ReturnRecord

RANGES = (3, 6, 12)
LIVE = ("issued", "paid")
ZERO = Decimal("0.00")


def parse_range(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 6
    return value if value in RANGES else 6


def _invoice_rows():
    """Issued/paid invoices with computed total and balance, using 4 queries total."""
    invoices = list(
        Invoice.objects.filter(status__in=LIVE).values(
            "id", "customer_id", "customer__name", "issue_date", "due_date", "tax_percent",
        )
    )
    subtotals = dict(
        InvoiceLine.objects.filter(invoice__status__in=LIVE)
        .values_list("invoice_id").annotate(s=Sum(_LINE_TOTAL))
    )
    paid = dict(
        Payment.objects.filter(is_voided=False, invoice__status__in=LIVE)
        .values_list("invoice_id").annotate(s=Sum("amount"))
    )
    credits = dict(
        CreditApplication.objects.filter(invoice__status__in=LIVE)
        .values_list("invoice_id").annotate(s=Sum("amount"))
    )
    rows = []
    for inv in invoices:
        subtotal = money(subtotals.get(inv["id"], ZERO))
        tax = money(subtotal * (inv["tax_percent"] or Decimal("0")) / Decimal("100"))
        total = subtotal + tax
        balance = money(total - money(paid.get(inv["id"], ZERO)) - money(credits.get(inv["id"], ZERO)))
        rows.append({**inv, "total": total, "balance": balance})
    return rows


def _by_month(pairs):
    """Sum (date, amount) pairs into {(y, m): Decimal}."""
    out = defaultdict(lambda: ZERO)
    for d, amount in pairs:
        if d is not None:
            out[month_key(d)] += Decimal(amount)
    return out


def _ageing(rows, today):
    buckets = [("Current", ZERO, "ok"), ("1–30 days", ZERO, "warn"),
               ("31–60 days", ZERO, "warn2"), ("61–90 days", ZERO, "bad"),
               ("90+ days", ZERO, "bad2")]
    totals = [ZERO] * 5
    overdue = ZERO
    for r in rows:
        if r["balance"] <= 0:
            continue
        days = (today - r["due_date"]).days if r["due_date"] else 0
        idx = 0 if days <= 0 else 1 if days <= 30 else 2 if days <= 60 else 3 if days <= 90 else 4
        totals[idx] += r["balance"]
        if idx:
            overdue += r["balance"]
    items = [{"label": b[0], "value": totals[i], "tone": b[2]} for i, b in enumerate(buckets)]
    return items, sum(totals, ZERO), overdue


def build_employee_dashboard(today=None):
    """A trimmed landing page for the Employee role.

    No customer names, revenue rankings or stock data — Employee accounts
    can't reach the Customers or Items screens, so the dashboard shouldn't
    surface that data either. Just counts and totals from the four areas
    they do work in: invoices, purchase orders, returns, damage reports.
    """
    today = today or timezone.localdate()
    month_start = today.replace(day=1)

    open_invoices = [inv for inv in Invoice.objects.filter(status__in=LIVE) if inv.balance_due > 0]
    outstanding_total = sum((inv.balance_due for inv in open_invoices), ZERO)
    draft_invoice_count = Invoice.objects.filter(status="draft").count()

    open_orders = list(PurchaseOrder.objects.filter(status__in=("draft", "ordered", "partial")))
    payable_total = sum(
        (po.balance_due for po in open_orders if po.status != "draft"), ZERO
    )

    return {
        "open_invoice_count": len(open_invoices),
        "outstanding_total": fmt_money(outstanding_total),
        "draft_invoice_count": draft_invoice_count,
        "open_order_count": len(open_orders),
        "payable_total": fmt_money(payable_total),
        "damages_this_month": DamageReport.objects.filter(date_reported__gte=month_start).count(),
        "returns_this_month": ReturnRecord.objects.filter(date_returned__gte=month_start).count(),
    }


def build_dashboard(range_months=6, today=None):
    today = today or timezone.localdate()
    months = month_starts(today, range_months)
    start = months[0]
    this_k, prev_k = month_key(months[-1]), month_key(month_starts(today, 2)[0])

    rows = _invoice_rows()

    # ---- Sales (invoice totals by issue month) ----
    sales = _by_month((r["issue_date"], r["total"]) for r in rows if r["issue_date"])

    # ---- Cash flow ----
    money_in = _by_month(
        Payment.objects.filter(is_voided=False, payment_date__gte=start)
        .values_list("payment_date", "amount")
    )
    money_out = _by_month(
        CreditNote.objects.filter(is_refunded=True, refund_date__gte=start)
        .values_list("refund_date", "amount")
    )

    # ---- Losses ----
    damage = _by_month(
        (d, qty * cost) for d, qty, cost in DamageReport.objects.filter(date_reported__gte=start)
        .values_list("date_reported", "quantity", "item__cost_price")
    )
    expiry = _by_month(
        (d, qty * cost) for d, qty, cost in ExpiryWriteOff.objects.filter(date_noticed__gte=start)
        .values_list("date_noticed", "quantity", "item__cost_price")
    )
    returns = _by_month(
        (timezone.localtime(created).date(), amount)
        for created, amount in CreditNote.objects.filter(
            return_record__isnull=False, created_at__date__gte=start
        ).values_list("created_at", "amount")
    )

    # ---- Receivables ageing ----
    ageing_items, receivables, overdue = _ageing(rows, today)

    # ---- Top customers / items (inside the selected window) ----
    cust = defaultdict(lambda: ZERO)
    for r in rows:
        if r["issue_date"] and r["issue_date"] >= start:
            cust[(r["customer_id"], r["customer__name"])] += r["total"]
    top_customers = sorted(cust.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_items = (
        InvoiceLine.objects.filter(invoice__status__in=LIVE, invoice__issue_date__gte=start)
        .values("item__name").annotate(rev=Sum(_LINE_TOTAL)).order_by("-rev")[:5]
    )

    # ---- Stock health ----
    stock_counts = {"ok": 0, "low": 0, "out": 0}
    for stock, reorder in Item.objects.annotate(
        stock=Coalesce(Sum("movements__quantity"), 0)
    ).values_list("stock", "reorder_level"):
        stock_counts["out" if stock <= 0 else "low" if stock <= reorder else "ok"] += 1

    # ---- KPIs ----
    rev_series = [sales.get(month_key(m), ZERO) for m in months]
    loss_series = [damage.get(month_key(m), ZERO) + expiry.get(month_key(m), ZERO) for m in months]
    rev_now, rev_prev = sales.get(this_k, ZERO), sales.get(prev_k, ZERO)
    loss_now = damage.get(this_k, ZERO) + expiry.get(this_k, ZERO)
    loss_prev = damage.get(prev_k, ZERO) + expiry.get(prev_k, ZERO)
    cash_now = money_in.get(this_k, ZERO)
    cash_series = [money_in.get(month_key(m), ZERO) for m in months]
    overdue_count = sum(
        1 for r in rows
        if r["balance"] > 0 and r["due_date"] and r["due_date"] < today
    )
    open_count = sum(1 for r in rows if r["balance"] > 0)

    kpis = [
        {"label": "Revenue this month", "value": fmt_money(rev_now), "delta": delta(rev_now, rev_prev),
         "good_up": True, "spark": sparkline(rev_series), "tone": "accent",
         "foot": f"vs {fmt_money(rev_prev)} last month"},
        {"label": "Cash received", "value": fmt_money(cash_now),
         "delta": delta(cash_now, money_in.get(prev_k, ZERO)), "good_up": True,
         "spark": sparkline(cash_series), "tone": "accent",
         "foot": "payments this month"},
        {"label": "Outstanding", "value": fmt_money(receivables), "delta": None, "spark": None,
         "tone": "neutral", "foot": f"{open_count} open invoice{'s' if open_count != 1 else ''}"},
        {"label": "Overdue", "value": fmt_money(overdue), "delta": None, "spark": None,
         "tone": "bad" if overdue > 0 else "neutral",
         "foot": f"{overdue_count} invoice{'s' if overdue_count != 1 else ''} past due"},
        {"label": "Stock loss this month", "value": fmt_money(loss_now),
         "delta": delta(loss_now, loss_prev), "good_up": False,
         "spark": sparkline(loss_series), "tone": "warn", "foot": "damaged + expired, at cost"},
    ]

    return {
        "range_months": range_months,
        "ranges": RANGES,
        "kpis": kpis,
        "sales_chart": column_chart(
            months, [{"key": "sales", "label": "Invoiced", "tone": "accent", "values": sales}],
            today=today),
        "cash_chart": column_chart(
            months,
            [{"key": "in", "label": "Money in", "tone": "accent", "values": money_in},
             {"key": "out", "label": "Refunds out", "tone": "muted", "values": money_out}],
            today=today),
        "loss_chart": column_chart(
            months,
            [{"key": "dmg", "label": "Damaged", "tone": "warn", "values": damage},
             {"key": "exp", "label": "Expired", "tone": "bad", "values": expiry},
             {"key": "ret", "label": "Returned", "tone": "muted", "values": returns}],
            stacked=True, today=today),
        "ageing_bars": rank_bars(ageing_items),
        "receivables_total": fmt_money(receivables),
        "top_customers": rank_bars([
            {"label": name, "value": value} for (_, name), value in top_customers
        ]),
        "top_items": rank_bars([
            {"label": r["item__name"], "value": money(r["rev"] or ZERO)} for r in top_items
        ]),
        "stock_health": segments([
            {"label": "In stock", "value": stock_counts["ok"], "tone": "ok"},
            {"label": "Low", "value": stock_counts["low"], "tone": "warn"},
            {"label": "Out", "value": stock_counts["out"], "tone": "bad"},
        ]),
    }
