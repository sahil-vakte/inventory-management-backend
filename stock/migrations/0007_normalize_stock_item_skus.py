import re

from django.db import migrations


def normalize_sku(value):
    value = str(value or '').strip()
    value = re.sub(r'\(([^()]*)\)', r'\1', value)
    value = value.replace('(', ' ').replace(')', ' ')
    return re.sub(r'\s+', ' ', value).strip()


def normalize_product_references(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.all():
        updates = {}
        for field in ('parent_reference', 'child_reference'):
            value = getattr(product, field)
            normalized = normalize_sku(value)
            if normalized != value:
                updates[field] = normalized
        if updates:
            for field, value in updates.items():
                setattr(product, field, value)
            product.save(update_fields=list(updates))


def merge_stock_item_values(target, source):
    merge_fields = [
        'reserved_stock',
        'minimum_stock_level',
        'maximum_stock_level',
        'available_stock_in_mtr',
    ]
    for field in merge_fields:
        setattr(target, field, max(getattr(target, field), getattr(source, field)))

    nullable_fields = [
        'warehouse_location',
        'supplier',
        'last_purchase_date',
        'notes',
        'primary_location_id',
        'secondary_location_id',
    ]
    for field in nullable_fields:
        if not getattr(target, field) and getattr(source, field):
            setattr(target, field, getattr(source, field))

    target.product_type = normalize_sku(target.product_type)
    if target.product_id is None and source.product_id is not None:
        target.product_id = source.product_id
    target.is_active = target.is_active or source.is_active
    target.is_discontinued = target.is_discontinued and source.is_discontinued
    target.is_deleted = target.is_deleted and source.is_deleted
    if not target.deleted_at and source.deleted_at:
        target.deleted_at = source.deleted_at
    target.save()


def update_related_stock_references(apps, old_sku, new_sku):
    StockMovement = apps.get_model('stock', 'StockMovement')
    StockBatch = apps.get_model('stock', 'StockBatch')
    OrderItem = apps.get_model('orders', 'OrderItem')

    StockMovement.objects.filter(stock_item_id=old_sku).update(stock_item_id=new_sku)
    StockBatch.objects.filter(stock_item_id=old_sku).update(stock_item_id=new_sku)
    OrderItem.objects.filter(stock_item_id=old_sku).update(stock_item_id=new_sku)
    OrderItem.objects.filter(sku=old_sku).update(sku=new_sku)


def normalize_stock_item_skus(apps, schema_editor):
    StockItem = apps.get_model('stock', 'StockItem')
    StockBatch = apps.get_model('stock', 'StockBatch')

    connection = schema_editor.connection
    constraints_disabled = connection.disable_constraint_checking()
    try:
        parenthesized_skus = (
            StockItem.objects.filter(sku__contains='(')
            | StockItem.objects.filter(sku__contains=')')
        )
        for source in list(parenthesized_skus.order_by('sku')):
            old_sku = source.sku
            new_sku = normalize_sku(old_sku)
            source.product_type = normalize_sku(source.product_type)

            if not new_sku or new_sku == old_sku:
                StockItem.objects.filter(sku=old_sku).update(product_type=source.product_type)
                continue

            target = StockItem.objects.filter(sku=new_sku).first()
            if target:
                merge_stock_item_values(target, source)
                update_related_stock_references(apps, old_sku, new_sku)
                source.delete()
                continue

            update_related_stock_references(apps, old_sku, new_sku)
            StockItem.objects.filter(sku=old_sku).update(
                sku=new_sku,
                product_type=source.product_type,
            )

        for batch in StockBatch.objects.all():
            normalized_sku = normalize_sku(batch.sku)
            if normalized_sku != batch.sku:
                batch.sku = normalized_sku
                batch.save(update_fields=['sku'])
    finally:
        if constraints_disabled:
            connection.enable_constraint_checking()
            connection.check_constraints()


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0006_normalize_stock_batch_sku'),
        ('orders', '0003_alter_orderstatushistory_from_status_and_more'),
        ('products', '0002_brand_deleted_at_brand_is_deleted_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_product_references, migrations.RunPython.noop),
        migrations.RunPython(normalize_stock_item_skus, migrations.RunPython.noop),
    ]
