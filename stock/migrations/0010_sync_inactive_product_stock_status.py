from django.db import migrations


def sync_inactive_product_stock_status(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    StockItem = apps.get_model('stock', 'StockItem')

    inactive_product_ids = Product.objects.filter(
        child_active=False,
    ).values_list('pk', flat=True)
    StockItem.objects.filter(product_id__in=inactive_product_ids).update(is_active=False)

    inactive_parent_ids = Product.objects.filter(
        parent_active=False,
    ).values_list('pk', flat=True)
    StockItem.objects.filter(product_id__in=inactive_parent_ids).update(is_active=False)

    deleted_product_ids = Product.objects.filter(
        is_deleted=True,
    ).values_list('pk', flat=True)
    StockItem.objects.filter(product_id__in=deleted_product_ids).update(
        is_active=False,
        is_deleted=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0009_create_missing_product_stock_items'),
        ('products', '0005_rename_product_ext_file_row_idx_product_ext_source__2d5d52_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(sync_inactive_product_stock_status, migrations.RunPython.noop),
    ]
