from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_employee_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='payment_instructions',
            field=models.TextField(blank=True, help_text='How customers should pay you (bank details, cheque payee, etc.). Copied onto each new invoice, where it can still be changed.'),
        ),
    ]
