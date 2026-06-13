from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_status_flow'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='lable_printed',
            field=models.BooleanField(default=False),
        ),
    ]
