from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_billed(self):
        return sum(inv.total for inv in self.invoices.filter(status='issued'))

    def total_paid(self):
        return sum(p.amount for inv in self.invoices.all() for p in inv.payments.all())

    def outstanding_balance(self):
        return self.total_billed() - self.total_paid()

    def credit_balance(self):
        return sum(c.remaining_amount for c in self.credit_notes.filter(is_applied=False))

    def __str__(self):
        return self.name