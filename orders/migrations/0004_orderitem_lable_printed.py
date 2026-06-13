from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_alter_orderstatushistory_from_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='lable_printed',
            field=models.BooleanField(default=False),
        ),
    ]
