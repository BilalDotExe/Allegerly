from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0005_invoice_payment_instructions'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='payment_terms',
            field=models.CharField(choices=[('due_on_receipt', 'Due on receipt'), ('net_15', 'Net 15'), ('net_30', 'Net 30'), ('net_45', 'Net 45'), ('net_60', 'Net 60')], default='net_30', max_length=20),
        ),
    ]
