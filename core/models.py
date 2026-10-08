from django.db import models


class CompanyProfile(models.Model):
    """Single-row table holding the business details printed on invoices."""

    name = models.CharField('Company name', max_length=200, default='Allegderly')
    address_line1 = models.CharField('Address line 1', max_length=200, blank=True)
    address_line2 = models.CharField('Address line 2', max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField('State / province', max_length=100, blank=True)
    postal_code = models.CharField('ZIP / postal code', max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    tax_id = models.CharField('Tax ID / registration no.', max_length=50, blank=True)
    invoice_footer = models.CharField(
        max_length=255, blank=True, default='Thank you for your business.',
        help_text='Printed at the bottom of every invoice.',
    )

    class Meta:
        verbose_name_plural = 'company profile'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @property
    def address_lines(self):
        locality = ', '.join(p for p in (self.city, self.state) if p)
        if self.postal_code:
            locality = f'{locality} {self.postal_code}'.strip()
        return [x for x in (self.address_line1, self.address_line2, locality, self.country) if x]

    def __str__(self):
        return self.name
