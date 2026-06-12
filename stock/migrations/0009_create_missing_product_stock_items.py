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


def stock_mtr(product):
    try:
        return max(0, int(product.stock_value or 0))
    except (TypeError, ValueError):
        return 0


def product_type(product):
    return normalize_reference(
        product.parent_reference or product.child_reference or f'VS{product.vs_child_id}'
    )[:20]


def unique_stock_sku(StockItem, product):
    base_sku = normalize_reference(
        product.child_reference or product.parent_reference or f'VS{product.vs_child_id}'
    )[:50]

    existing = StockItem.objects.filter(sku=base_sku).first()
    if existing is None or existing.product_id == product.pk:
        return base_sku

    suffix = f' {product.vs_child_id}'
    candidate = f'{base_sku[:50 - len(suffix)]}{suffix}'
    existing = StockItem.objects.filter(sku=candidate).first()
    if existing is None or existing.product_id == product.pk:
        return candidate

    return f'VS{product.vs_child_id}'[:50]


def ensure_product_stock_items(apps, schema_editor):
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
        stock_item = StockItem.objects.filter(product_id=product.pk).order_by('sku').first()

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

        defaults = {
            'product_type': product_type(product),
            'color_id': stock_color.pk,
            'minimum_stock_level': product.min_purchase_quantity or 0,
            'maximum_stock_level': product.max_purchase_quantity or 0,
            'warehouse_location': product.pick_location,
            'unit_cost': product.cost_price_inc_vat or 0,
            'last_purchase_price': product.cost_price_inc_vat or 0,
            'is_active': active,
            'is_deleted': bool(product.is_deleted),
        }

        if stock_item is not None:
            StockItem.objects.filter(pk=stock_item.pk).update(**defaults)
            continue

        StockItem.objects.create(
            sku=unique_stock_sku(StockItem, product),
            product_id=product.pk,
            available_stock_in_mtr=stock_mtr(product),
            reserved_stock=0,
            **defaults,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0008_cleanup_remaining_parenthesized_stock_references'),
        ('colors', '0001_initial'),
        ('products', '0002_brand_deleted_at_brand_is_deleted_and_more'),
    ]

    operations = [
        migrations.RunPython(ensure_product_stock_items, migrations.RunPython.noop),
    ]
