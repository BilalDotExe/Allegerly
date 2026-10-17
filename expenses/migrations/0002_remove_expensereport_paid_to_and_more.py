from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='expensereport',
            name='paid_to',
        ),
        migrations.RemoveField(
            model_name='expensereport',
            name='payment_method',
        ),
        migrations.RemoveField(
            model_name='expensereport',
            name='reference',
        ),
        migrations.AddField(
            model_name='expenseline',
            name='reference',
            field=models.CharField(blank=True, help_text='Receipt, cheque or transfer reference.', max_length=100),
        ),
        migrations.AlterField(
            model_name='expensereport',
            name='name',
            field=models.CharField(max_length=200, verbose_name='Title'),
        ),
    ]
