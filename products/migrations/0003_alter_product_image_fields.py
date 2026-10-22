# Generated manually for Visualsoft image exports.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_brand_deleted_at_brand_is_deleted_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='parent_product_images',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='child_product_images',
            field=models.TextField(blank=True, null=True),
        ),
    ]
