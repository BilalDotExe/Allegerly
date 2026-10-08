from django.core.exceptions import ValidationError
from django.db import transaction

from audit.services import log as audit_log
from core.money import money
from .models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchasePayment


def _ensure_not_below_paid(po):
    if po.total < po.total_paid:
        raise ValidationError(
            f"These changes would bring the order total (${po.total}) below what has already "
            f"been paid (${po.total_paid})."
        )


@transaction.atomic
def create_order(form, formset, user, request=None):
    po = form.save(commit=False)
    po.created_by = user
    po.save()
    formset.instance = po
    formset.save()
    audit_log(user, "po_created", po, request=request)
    return po


@transaction.atomic
def update_order(form, formset, user, request=None):
    """Save header and line edits together; refuse edits that bring the total below what is paid."""
    po = form.save()
    formset.instance = po
    formset.save()
    _ensure_not_below_paid(po)
    changes = {
        "fields": list(form.changed_data),
        "lines_changed": len(formset.changed_objects),
        "lines_added": len(formset.new_objects),
        "lines_removed": len(formset.deleted_objects),
    }
    audit_log(user, "po_updated", po, changes=changes, request=request)
    return po


@transaction.atomic
def place_order(po: PurchaseOrder, user, request=None):
    if po.status != "draft":
        raise ValidationError("Only draft purchase orders can be placed.")
    if not po.lines.exists():
        raise ValidationError("Cannot place a purchase order with no lines.")
    po.status = "ordered"
    po.save(update_fields=["status"])
    audit_log(user, "po_placed", po, request=request)
    return po


@transaction.atomic
def receive_goods(po: PurchaseOrder, received_date, lines, user, note="", request=None):
    """
    Record a delivery. `lines` is a list of dicts: po_line, quantity, unit_cost.
    Prices may differ from the order; the new price becomes the line's price.
    """
    if not po.can_receive:
        raise ValidationError("Only ordered or partially received purchase orders can receive goods.")
    lines = [line for line in lines if line["quantity"] > 0]
    if not lines:
        raise ValidationError("Enter a quantity for at least one line.")

    receipt = GoodsReceipt.objects.create(
        purchase_order=po, received_date=received_date, note=note, created_by=user,
    )
    detail = []
    for entry in lines:
        po_line = entry["po_line"]
        qty = entry["quantity"]
        cost = money(entry["unit_cost"])
        if qty > po_line.outstanding_qty:
            raise ValidationError(f"{po_line.item_name}: only {po_line.outstanding_qty} still outstanding.")

        GoodsReceiptLine.objects.create(receipt=receipt, po_line=po_line, quantity=qty, unit_cost=cost)
        row = {"item": po_line.item_name, "qty": qty}
        if cost != po_line.unit_cost:
            row["price"] = f"{po_line.unit_cost} -> {cost}"
            po_line.unit_cost = cost
            po_line.save(update_fields=["unit_cost"])
        detail.append(row)

    all_received = all(line.outstanding_qty == 0 for line in po.lines.all())
    po.status = "received" if all_received else "partial"
    po.save(update_fields=["status"])
    _ensure_not_below_paid(po)

    audit_log(user, "po_received", po, changes={"receipt": receipt.receipt_number, "lines": detail}, request=request)
    return receipt


@transaction.atomic
def close_order(po: PurchaseOrder, user, request=None):
    """Accept a short delivery: mark a partly received order as complete."""
    if po.status != "partial":
        raise ValidationError("Only partially received orders can be closed short.")
    po.status = "received"
    po.save(update_fields=["status"])
    audit_log(user, "po_closed_short", po, changes={"received": po.qty_received, "ordered": po.qty_ordered}, request=request)
    return po


@transaction.atomic
def cancel_order(po: PurchaseOrder, user, reason: str, request=None):
    if po.status not in ("draft", "ordered"):
        raise ValidationError("Only draft or ordered purchase orders can be cancelled.")
    if po.receipts.exists():
        raise ValidationError("Goods have already been received against this order.")
    if po.payments.exists():
        raise ValidationError("Payments have been recorded against this order, so it cannot be cancelled.")
    po.status = "cancelled"
    po.cancel_reason = reason
    po.save(update_fields=["status", "cancel_reason"])
    audit_log(user, "po_cancelled", po, changes={"reason": reason}, request=request)
    return po


@transaction.atomic
def record_purchase_payment(po: PurchaseOrder, amount, method, payment_date, user,
                            reference="", note="", request=None):
    if po.status in ("draft", "cancelled"):
        raise ValidationError("Cannot record a payment on a draft or cancelled purchase order.")
    if amount <= 0:
        raise ValidationError("Payment amount must be positive.")
    if amount > po.balance_due:
        raise ValidationError("Payment exceeds the balance due.")

    payment = PurchasePayment.objects.create(
        purchase_order=po, amount=amount, method=method, payment_date=payment_date,
        reference=reference, note=note, created_by=user,
    )
    audit_log(user, "po_payment_recorded", payment, changes={"amount": str(amount), "method": method}, request=request)
    return payment
