import re

from colors.models import Color
from products.models import Product
from stock.models import StockItem
from stock.sku_utils import normalize_sku_reference


UNKNOWN_COLOR_CODE = 'UNKNOWN'


def sync_product_stock_items(dry_run=False):
    """Ensure every product has at least one stock item."""
    stats = {
        'products_seen': 0,
        'stock_created': 0,
        'stock_updated': 0,
        'stock_unchanged': 0,
    }

    unknown_color = _get_or_create_unknown_color(dry_run)

    for product in Product.all_objects.all().order_by('vs_child_id'):
        stats['products_seen'] += 1
        stock_items = list(StockItem.all_objects.filter(product=product).order_by('sku'))
        desired = _stock_defaults_for_product(
            product,
            unknown_color,
            create_stock=not stock_items,
            dry_run=dry_run,
        )

        if stock_items:
            changed_any = False
            updates = {
                field: value
                for field, value in desired.items()
                if field not in {'available_stock_in_mtr', 'reserved_stock'}
            }

            for stock_item in stock_items:
                changed_fields = {
                    field: value
                    for field, value in updates.items()
                    if getattr(stock_item, field) != value
                }
                if not changed_fields:
                    continue
                changed_any = True
                if not dry_run:
                    for field, value in changed_fields.items():
                        setattr(stock_item, field, value)
                    stock_item.save(update_fields=[*changed_fields.keys(), 'updated_at'])

            if changed_any:
                stats['stock_updated'] += len(stock_items)
            else:
                stats['stock_unchanged'] += len(stock_items)
            continue

        sku = _unique_stock_sku_for_product(product)
        if not dry_run:
            StockItem.all_objects.create(sku=sku, **desired)
        stats['stock_created'] += 1

    return stats


def _stock_defaults_for_product(product, unknown_color, create_stock=False, dry_run=False):
    is_active = bool(product.child_active and product.parent_active and not product.is_deleted)
    defaults = {
        'product_type': _product_type(product),
        'product': product,
        'color': _color_for_product(product, unknown_color, dry_run=dry_run),
        'minimum_stock_level': product.min_purchase_quantity or 0,
        'maximum_stock_level': product.max_purchase_quantity or 0,
        'warehouse_location': product.pick_location,
        'unit_cost': product.cost_price_inc_vat or 0,
        'last_purchase_price': product.cost_price_inc_vat or 0,
        'is_active': is_active,
        'is_deleted': bool(product.is_deleted),
    }
    if create_stock:
        defaults['available_stock_in_mtr'] = _stock_mtr_from_product(product)
        defaults['reserved_stock'] = 0
    return defaults


def _unique_stock_sku_for_product(product):
    base_sku = normalize_sku_reference(
        product.child_reference or product.parent_reference or f'VS{product.vs_child_id}'
    )[:50]

    existing = StockItem.all_objects.filter(sku=base_sku).first()
    if existing is None or existing.product_id == product.pk:
        return base_sku

    suffix = f' {product.vs_child_id}'
    candidate = f'{base_sku[:50 - len(suffix)]}{suffix}'
    existing = StockItem.all_objects.filter(sku=candidate).first()
    if existing is None or existing.product_id == product.pk:
        return candidate

    return f'VS{product.vs_child_id}'[:50]


def _product_type(product):
    return normalize_sku_reference(
        product.parent_reference or product.child_reference or f'VS{product.vs_child_id}'
    )[:20]


def _stock_mtr_from_product(product):
    try:
        return max(0, int(product.stock_value or 0))
    except (TypeError, ValueError):
        return 0


def _color_for_product(product, unknown_color, dry_run=False):
    color_name = _first_list_value(product.tag_colours or product.attribute_colour)
    if not color_name:
        return unknown_color

    color_code = _color_code(color_name)
    if dry_run:
        return (
            Color.all_objects.filter(color_code=color_code).first()
            or Color(color_code=color_code, color_name=color_name[:100])
        )
    color, _ = Color.all_objects.update_or_create(
        color_code=color_code,
        defaults={
            'color_name': color_name[:100],
            'is_deleted': False,
            'deleted_at': None,
        },
    )
    return color


def _get_or_create_unknown_color(dry_run=False):
    if dry_run:
        return Color(color_code=UNKNOWN_COLOR_CODE, color_name='Unknown')
    color, _ = Color.all_objects.update_or_create(
        color_code=UNKNOWN_COLOR_CODE,
        defaults={
            'color_name': 'Unknown',
            'is_deleted': False,
            'deleted_at': None,
        },
    )
    return color


def _first_list_value(value):
    value = str(value or '').strip()
    if not value:
        return None
    for part in re.split(r'[\n,;/|]+', value):
        part = part.strip()
        if part:
            return part
    return None


def _color_code(color_name):
    normalized = re.sub(r'[^A-Za-z0-9]+', '', color_name or '').upper()
    return normalized[:10] or UNKNOWN_COLOR_CODE
