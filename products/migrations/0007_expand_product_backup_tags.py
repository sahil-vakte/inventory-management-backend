from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('products', '0006_add_product_short_title')]

    operations = [
        migrations.AlterField(
            model_name='product', name='tag_colours',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='product', name='tag_print_texture',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
