import re

from django.db import migrations


def normalize_reference(value):
    value = str(value or '').strip()
    value = re.sub(r'\(([^()]*)\)', r'\1', value)
    value = value.replace('(', ' ').replace(')', ' ')
    return re.sub(r'\s+', ' ', value).strip()


def cleanup_remaining_references(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    StockItem = apps.get_model('stock', 'StockItem')
    StockBatch = apps.get_model('stock', 'StockBatch')
    OrderItem = apps.get_model('orders', 'OrderItem')

    for product in Product.objects.all():
        updates = {}
        for field in ('parent_reference', 'child_reference'):
            current = getattr(product, field)
            normalized = normalize_reference(current)
            if normalized != current:
                updates[field] = normalized
        if updates:
            Product.objects.filter(pk=product.pk).update(**updates)

    for stock_item in StockItem.objects.all():
        normalized_type = normalize_reference(stock_item.product_type)[:20]
        if normalized_type != stock_item.product_type:
            StockItem.objects.filter(pk=stock_item.pk).update(product_type=normalized_type)

    for batch in StockBatch.objects.all():
        normalized_sku = normalize_reference(batch.sku)
        if normalized_sku != batch.sku:
            StockBatch.objects.filter(pk=batch.pk).update(sku=normalized_sku)

    for item in OrderItem.objects.all():
        normalized_sku = normalize_reference(item.sku)[:50]
        if normalized_sku != item.sku:
            OrderItem.objects.filter(pk=item.pk).update(sku=normalized_sku)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0007_normalize_stock_item_skus'),
        ('orders', '0003_alter_orderstatushistory_from_status_and_more'),
        ('products', '0002_brand_deleted_at_brand_is_deleted_and_more'),
    ]

    operations = [
        migrations.RunPython(cleanup_remaining_references, migrations.RunPython.noop),
    ]
