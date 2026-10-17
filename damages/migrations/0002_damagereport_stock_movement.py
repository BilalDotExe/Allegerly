import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('damages', '0001_initial'),
        ('inventory', '0003_expirywriteoff'),
    ]

    operations = [
        migrations.AddField(
            model_name='damagereport',
            name='stock_movement',
            field=models.OneToOneField(blank=True, help_text='Set once this damage has been reconciled with a manual stock adjustment.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='damage_report', to='inventory.stockmovement'),
        ),
    ]
