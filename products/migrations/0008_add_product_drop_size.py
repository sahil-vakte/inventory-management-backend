from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('products', '0007_expand_product_backup_tags')]

    operations = [
        migrations.AddField(
            model_name='product', name='attribute_drop_size',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='productextendeddata', name='attribute_13_drop_size',
            field=models.TextField(blank=True, db_column='Attribute 13 (Drop Size)', null=True),
        ),
    ]
