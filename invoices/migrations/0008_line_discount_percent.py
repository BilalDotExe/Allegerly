from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0007_invoice_discount_percent'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='invoice',
            name='discount_percent',
        ),
        migrations.AddField(
            model_name='invoiceline',
            name='discount_percent',
            field=models.DecimalField(blank=True, decimal_places=2, default=Decimal('0.00'), max_digits=5),
        ),
    ]
