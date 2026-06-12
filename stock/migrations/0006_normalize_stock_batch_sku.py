import re

from django.db import migrations


def normalize_sku(value):
    value = str(value or '').strip()
    value = re.sub(r'\(([^()]*)\)', r'\1', value)
    return re.sub(r'\s+', ' ', value).strip()


def normalize_stock_batch_skus(apps, schema_editor):
    StockBatch = apps.get_model('stock', 'StockBatch')
    for batch in StockBatch.objects.all():
        normalized_sku = normalize_sku(batch.sku)
        if normalized_sku != batch.sku:
            batch.sku = normalized_sku
            batch.save(update_fields=['sku'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0005_stock_batch_incoming'),
    ]

    operations = [
        migrations.RunPython(normalize_stock_batch_skus, migrations.RunPython.noop),
    ]
