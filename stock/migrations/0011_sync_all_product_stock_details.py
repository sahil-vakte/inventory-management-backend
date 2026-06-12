import re

from django.db import migrations


UNKNOWN_COLOR_CODE = 'UNKNOWN'


def normalize_reference(value):
    value = str(value or '').strip()
    value = re.sub(r'\(([^()]*)\)', r'\1', value)
    value = value.replace('(', ' ').replace(')', ' ')
    return re.sub(r'\s+', ' ', value).strip()


def color_code(color_name):
    normalized = re.sub(r'[^A-Za-z0-9]+', '', color_name or '').upper()
    return normalized[:10] or UNKNOWN_COLOR_CODE


def first_list_value(value):
    value = str(value or '').strip()
    if not value:
        return None
    for part in re.split(r'[\n,;/|]+', value):
        part = part.strip()
        if part:
            return part
    return None


def product_type(product):
    return normalize_reference(
        product.parent_reference or product.child_reference or f'VS{product.vs_child_id}'
    )[:20]


def sync_all_product_stock_details(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    StockItem = apps.get_model('stock', 'StockItem')
    Color = apps.get_model('colors', 'Color')

    unknown_color, _ = Color.objects.update_or_create(
        color_code=UNKNOWN_COLOR_CODE,
        defaults={
            'color_name': 'Unknown',
            'is_deleted': False,
            'deleted_at': None,
        },
    )

    for product in Product.objects.all().order_by('vs_child_id'):
        active = bool(product.child_active and product.parent_active and not product.is_deleted)
        color_name = first_list_value(product.tag_colours or product.attribute_colour)
        stock_color = unknown_color
        if color_name:
            stock_color, _ = Color.objects.update_or_create(
                color_code=color_code(color_name),
                defaults={
                    'color_name': color_name[:100],
                    'is_deleted': False,
                    'deleted_at': None,
                },
            )

        StockItem.objects.filter(product_id=product.pk).update(
            product_type=product_type(product),
            color_id=stock_color.pk,
            minimum_stock_level=product.min_purchase_quantity or 0,
            maximum_stock_level=product.max_purchase_quantity or 0,
            warehouse_location=product.pick_location,
            unit_cost=product.cost_price_inc_vat or 0,
            last_purchase_price=product.cost_price_inc_vat or 0,
            is_active=active,
            is_deleted=bool(product.is_deleted),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0010_sync_inactive_product_stock_status'),
        ('colors', '0001_initial'),
        ('products', '0005_rename_product_ext_file_row_idx_product_ext_source__2d5d52_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(sync_all_product_stock_details, migrations.RunPython.noop),
    ]
