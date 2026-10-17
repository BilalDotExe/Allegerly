import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('damages', '0002_damagereport_stock_movement'),
        ('invoices', '0008_line_discount_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='creditnote',
            name='damage_report',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='credit_note', to='damages.damagereport'),
        ),
    ]
