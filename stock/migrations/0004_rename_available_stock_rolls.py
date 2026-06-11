from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0003_stockitem_primary_location_stockitem_product_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='stockitem',
            old_name='available_stock_rolls',
            new_name='available_stock_in_mtr',
        ),
        migrations.AlterField(
            model_name='stockitem',
            name='available_stock_in_mtr',
            field=models.IntegerField(default=0, help_text='Available stock in metres'),
        ),
        migrations.RemoveIndex(
            model_name='stockitem',
            name='stock_availab_95624e_idx',
        ),
        migrations.AddIndex(
            model_name='stockitem',
            index=models.Index(fields=['available_stock_in_mtr'], name='stock_availab_95624e_idx'),
        ),
    ]
