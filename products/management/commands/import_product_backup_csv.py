import csv
import hashlib
import json
import logging
import re
from contextlib import contextmanager, nullcontext
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from colors.models import Color
from products.models import Brand, Category, Location, Product, ProductExtendedData
from stock.models import StockItem, StockMovement
from stock.sku_utils import normalize_sku_reference

logger = logging.getLogger(__name__)


FINALIZED_COLUMNS = {
    'VS Parent ID',
    'VS Child ID',
    'Parent Reference',
    'Available On This Website',
    'Parent Product Title',
    'Child Product Title',
    'ShortTitle',
    'Attribute 13 (Drop Size)',
    'Product Subtitle',
    'Product Summary',
    'Product Description',
    'Categories',
    'Attribute 1 (Length)',
    'Allow Sample Request',
    'Sample Request Cost',
    'Tag 2 (Colours)',
    'Tag 3 (Material)',
    'Tag 1 (Print/ Texture)',
    'Parent Product Sash',
    'RRP Price (Inc VAT)',
    'Cost Price (Inc VAT)',
    'VAT Rate',
    'Display On Sale Page',
    'Price Break 1 (Quantity)',
    'Price Break 1 (Price Inc VAT)',
    'Price Break 1 (Sale Price Inc VAT)',
    'Price Break 1 (Deposit Price Inc VAT)',
    'Price Break 1 (Allow Further Discounts Inc VAT)',
    'Price Break 2 (Quantity)',
    'Price Break 2 (Price Inc VAT)',
    'Price Break 2 (Sale Price Inc VAT)',
    'Price Break 2 (Deposit Price Inc VAT)',
    'Price Break 2 (Allow Further Discounts Inc VAT)',
    'Price Break 3 (Quantity)',
    'Price Break 3 (Price Inc VAT)',
    'Price Break 3 (Sale Price Inc VAT)',
    'Price Break 3 (Deposit Price Inc VAT)',
    'Price Break 3 (Allow Further Discounts Inc VAT)',
    'Price Break 4 (Quantity)',
    'Price Break 4 (Price Inc VAT)',
    'Price Break 4 (Sale Price Inc VAT)',
    'Price Break 4 (Deposit Price Inc VAT)',
    'Price Break 4 (Allow Further Discounts Inc VAT)',
    'Price Break 5 (Quantity)',
    'Price Break 5 (Price Inc VAT)',
    'Price Break 5 (Sale Price Inc VAT)',
    'Price Break 5 (Deposit Price Inc VAT)',
    'Price Break 5 (Allow Further Discounts Inc VAT)',
    'Stock Value',
    'Weight (in KGs)',
    'Parent Product Url',
    'Child Product Url',
    'Parent Product Images',
    'Child Product Images',
    'Meta Title',
    'Meta Keywords',
    'Meta Description',
}


EXTENDED_METADATA_FIELDS = {
    'id',
    'product',
    'source_file_name',
    'source_file_date',
    'row_number',
    'row_hash',
    'import_batch_id',
    'raw_data',
    'raw_headers',
    'is_active',
    'created_at',
    'updated_at',
}

CSV_ENCODINGS = ('utf-8-sig', 'cp1252', 'latin-1')

# Columns not represented by Product are retained in ProductExtendedData.raw_data.
PRODUCT_COLUMNS = {
    'vs_parent_id': 'VS Parent ID',
    'parent_reference': 'Parent Reference',
    'child_reference': ('Child Reference', 'Child'),
    'parent_product_title': 'Parent Product Title',
    'child_product_title': 'Child Product Title',
    'short_title': ('ShortTitle', 'Short Title', 'short_title'),
    'product_subtitle': 'Product Subtitle',
    'product_summary': 'Product Summary',
    'product_description': 'Product Description',
    'available_on_this_website': 'Available On This Website',
    'attribute_length': 'Attribute 1 (Length)',
    'attribute_colour': 'Attribute 2 (Colour)',
    'attribute_top_sizes': 'Attribute 3 (Top Sizes)',
    'attribute_dress_sizes': 'Attribute 4 (Dress Sizes)',
    'attribute_design': 'Attribute 5 (Design)',
    'attribute_print': 'Attribute 6 (Print)',
    'attribute_weight': 'Attribute 7 (Weight)',
    'attribute_width': 'Attribute 8 (Width)',
    'attribute_size': ('Attribute 9 (Size)', 'Attribute 8 (Size)'),
    'attribute_choose_type': 'Attribute 10 (Choose Type)',
    'attribute_gift_card_value': 'Attribute 11 (Gift Card Value)',
    'attribute_colours_pf': 'Attribute 12 (Colours PF)',
    'attribute_drop_size': 'Attribute 13 (Drop Size)',
    'allow_sample_request': 'Allow Sample Request',
    'sample_request_cost': 'Sample Request Cost',
    'tag_colours': 'Tag 2 (Colours)',
    'tag_matching_lycra_mesh': 'Tag 8 (Matching Lycra & Mesh )',
    'tag_material': 'Tag 3 (Material)',
    'tag_materials': 'Tag 11 (Materials)',
    'tag_print_texture': 'Tag 1 (Print/ Texture)',
    'tag_quantity_box': 'Tag 6 (Quantity Box)',
    'tag_trimmings': 'Tag 4 (Trimmings)',
    'release_date': 'Release Date',
    'available_now': 'Available Now',
    'date_added': 'Date Added',
    'parent_product_sash': 'Parent Product Sash',
    'deposit_price_inc_vat': 'Deposit Price (Inc VAT)',
    'rrp_price_inc_vat': 'RRP Price (Inc VAT)',
    'cost_price_inc_vat': 'Cost Price (Inc VAT)',
    'vat_rate': 'VAT Rate',
    'stock_value': 'Stock Value',
    'min_purchase_quantity': 'Min Purchase Quantity',
    'max_purchase_quantity': 'Max Purchase Quantity',
    'minimum_age': 'Minimum Age',
    'pick_location': 'Pick Location',
    'stock_message': 'Stock Message',
    'weight_kg': 'Weight (in KGs)',
    'child_active': 'Child Active',
    'parent_active': 'Parent Active',
    'archive_delete': 'Archive (Delete)',
    'archive_redirect_url': 'Archive Redirect URL',
    'parent_product_url': 'Parent Product Url',
    'child_product_url': 'Child Product Url',
    'parent_product_images': 'Parent Product Images',
    'child_product_images': 'Child Product Images',
    'meta_title': 'Meta Title',
    'meta_keywords': 'Meta Keywords',
    'meta_description': 'Meta Description',
    'display_on_sale_page': 'Display On Sale Page',
    'featured': 'Featured',
    'trade_only_product': 'Trade Only Product',
}
for _number in range(1, 6):
    for _suffix, _label in (
        ('quantity', 'Quantity'), ('price', 'Price Inc VAT'),
        ('sale_price', 'Sale Price Inc VAT'), ('deposit_price', 'Deposit Price Inc VAT'),
        ('allow_further_discounts', 'Allow Further Discounts Inc VAT'),
    ):
        PRODUCT_COLUMNS[f'price_break_{_number}_{_suffix}'] = f'Price Break {_number} ({_label})'


class Command(BaseCommand):
    help = (
        'Import product backup XLSX/CSV files, updating changed products and live stock '
        'without deleting products. Use --dry-run to preview without writing.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to product backup XLSX, XLS, or CSV')
        parser.add_argument('--batch-id', default=None, help='Import batch identifier')
        parser.add_argument('--chunk-size', type=int, default=500, help='Rows to process per transaction')
        parser.add_argument('--limit', type=int, default=None, help='Optional maximum number of data rows to read')
        parser.add_argument('--dry-run', action='store_true', help='Validate and report without writing')
        parser.add_argument(
            '--clear-blank-locations', action='store_true',
            help='Explicitly clear existing primary/warehouse locations when Pick Location is blank',
        )
        parser.add_argument(
            '--skip-products',
            action='store_true',
            help='Only save ProductExtendedData rows; do not create/update Product rows',
        )

    def handle(self, *args, **options):
        file_path = Path(options['file'])
        if not file_path.exists():
            raise CommandError(f'File not found: {file_path}')

        stats = self.import_file(
            file_path=file_path,
            batch_id=options['batch_id'],
            chunk_size=options['chunk_size'],
            limit=options['limit'],
            dry_run=options['dry_run'],
            skip_products=options['skip_products'],
            clear_blank_locations=options['clear_blank_locations'],
            write_output=True,
        )

        self.stdout.write(self.style.SUCCESS('Import scan complete.'))
        for key, value in stats.items():
            self.stdout.write(f'{key}: {value}')
        if stats['errors']:
            raise CommandError('Some product rows failed validation. Review error_examples before importing.')

    def import_file(
        self, file_path, batch_id=None, chunk_size=500, limit=None,
        dry_run=False, skip_products=False, write_output=False, clear_blank_locations=False,
        source_file_name=None
    ):
        file_path = Path(file_path)
        if not file_path.exists():
            raise CommandError(f'File not found: {file_path}')

        batch_id = str(batch_id or timezone.now().strftime('%Y%m%d%H%M%S'))
        if len(batch_id) > 100:
            raise CommandError('batch_id must be at most 100 characters')
        if limit is not None and limit < 1:
            raise CommandError('limit must be a positive number, or omitted for all rows')
        chunk_size = max(1, chunk_size)
        source_file_name = source_file_name or file_path.name
        source_date = self._source_date_from_name(source_file_name)
        self.clear_blank_locations = clear_blank_locations
        self._preview_stock_skus = {}
        self._seen_product_ids = set()
        self._related_cache = {}

        stats = {
            'batch_id': batch_id,
            'source_file_name': source_file_name,
            'rows_seen': 0,
            'products_created': 0,
            'products_updated': 0,
            'products_unchanged': 0,
            'brands_created': 0,
            'brands_updated': 0,
            'categories_created': 0,
            'categories_updated': 0,
            'colors_created': 0,
            'colors_updated': 0,
            'locations_created': 0,
            'locations_updated': 0,
            'stock_created': 0,
            'stock_updated': 0,
            'stock_unchanged': 0,
            'stock_quantities_changed': 0,
            'stock_locations_changed': 0,
            'extended_created': 0,
            'extended_updated': 0,
            'extended_skipped': 0,
            'invalid_product_rows': 0,
            'errors': 0,
            'warnings': 0,
            'warning_examples': [],
            'error_examples': [],
            'change_examples': [],
        }
        self._stats = stats

        if write_output:
            self.stdout.write(
                f"Importing {source_file_name} with batch '{batch_id}'"
                + (' (dry run)' if dry_run else '')
            )
        with self._read_rows(file_path, write_output) as (source_headers, reader):

            header_specs = self._build_header_specs(source_headers)
            self._validate_extended_model_columns(header_specs)

            chunk = []
            for row_number, values in enumerate(reader, start=2):
                if not any(self._clean(value) is not None for value in values):
                    continue
                if limit is not None and stats['rows_seen'] >= limit:
                    break
                stats['rows_seen'] += 1
                chunk.append((row_number, values))
                if len(chunk) >= chunk_size:
                    self._process_chunk(
                        chunk, header_specs, source_file_name, source_date,
                        batch_id, dry_run, skip_products, stats, write_output
                    )
                    chunk = []
                    if write_output:
                        self.stdout.write(f"Processed {stats['rows_seen']} rows; errors: {stats['errors']}")

            if chunk:
                self._process_chunk(
                    chunk, header_specs, source_file_name, source_date,
                    batch_id, dry_run, skip_products, stats, write_output
                )

        return stats

    @contextmanager
    def _read_rows(self, file_path, write_output=False):
        suffix = file_path.suffix.lower()
        if suffix == '.csv':
            encoding = self._detect_csv_encoding(file_path)
            if write_output:
                self.stdout.write(f'Reading CSV using {encoding} encoding')
            with file_path.open('r', encoding=encoding, newline='') as handle:
                reader = csv.reader(handle)
                headers = next(reader, None)
                if headers is None:
                    raise CommandError('Product file is empty')
                yield headers, reader
        elif suffix == '.xlsx':
            from openpyxl import load_workbook

            workbook = load_workbook(file_path, read_only=True, data_only=True)
            try:
                sheet_name = next(
                    (name for name in ('Products', 'Product Master') if name in workbook.sheetnames),
                    None,
                )
                if sheet_name is None:
                    raise CommandError('Workbook must contain a Products or Product Master sheet')
                if write_output:
                    self.stdout.write(f'Reading worksheet {sheet_name}')
                reader = workbook[sheet_name].iter_rows(values_only=True)
                headers = next(reader, None)
                if headers is None:
                    raise CommandError('Product sheet is empty')
                yield headers, reader
            finally:
                workbook.close()
        elif suffix == '.xls':
            import pandas as pd

            with pd.ExcelFile(file_path) as workbook:
                sheet_name = next(
                    (name for name in ('Products', 'Product Master') if name in workbook.sheet_names),
                    None,
                )
                if sheet_name is None:
                    raise CommandError('Workbook must contain a Products or Product Master sheet')
                frame = workbook.parse(sheet_name, dtype=object).where(pd.notna, None)
                yield [None if str(h).startswith('Unnamed:') else h for h in frame.columns], frame.itertuples(index=False, name=None)
        else:
            raise CommandError('File must be XLSX, XLS, or CSV')

    def _detect_csv_encoding(self, file_path):
        """Use strict decoding so product text is not silently corrupted."""
        for encoding in CSV_ENCODINGS:
            try:
                with file_path.open('r', encoding=encoding, newline='') as handle:
                    while handle.read(1024 * 1024):
                        pass
                return encoding
            except UnicodeDecodeError:
                continue

        raise CommandError(
            'CSV could not be decoded as UTF-8, Windows-1252, or Latin-1.'
        )

    def _process_chunk(
        self, chunk, header_specs, source_file_name, source_date,
        batch_id, dry_run, skip_products, stats, write_output=False
    ):
        extended_rows = []

        for row_number, values in chunk:
            row_data = self._row_data(header_specs, values)
            raw_payload = {
                spec['db_column']: row_data.get(spec['db_column'])
                for spec in header_specs
            }
            row_hash = self._row_hash(raw_payload)

            product = None
            if not skip_products:
                try:
                    self._current_row = row_number
                    self._pending_related = {}
                    with nullcontext() if dry_run else transaction.atomic():
                        product, product_action, product_fields, product_stats = self._upsert_product(row_data, dry_run)
                        stock_item, stock_action, stock_fields, stock_stats = self._upsert_stock_item(
                            row_data, product, dry_run, batch_id
                        )
                    self._merge_stats(stats, product_stats)
                    self._merge_stats(stats, stock_stats)
                    self._related_cache.update(self._pending_related)
                    stats[f'products_{product_action}'] += 1
                    stats[f'stock_{stock_action}'] += 1
                    if 'available_stock_in_mtr' in stock_fields:
                        stats['stock_quantities_changed'] += 1
                    if {'primary_location', 'warehouse_location'} & set(stock_fields):
                        stats['stock_locations_changed'] += 1
                    self._preview_stock_skus[stock_item.sku] = product.pk
                    if product_action != 'unchanged' or stock_action != 'unchanged':
                        self._example('change_examples', {
                            'row_number': row_number, 'vs_child_id': product.pk,
                            'product_action': product_action, 'product_fields': product_fields,
                            'stock_action': stock_action, 'stock_fields': stock_fields,
                        })
                except Exception as exc:
                    product = None
                    stats['errors'] += 1
                    stats['invalid_product_rows'] += 1
                    self._example('error_examples', {
                        'row_number': row_number, 'vs_child_id': row_data.get('VS Child ID'),
                        'error': str(exc)[:1000],
                    })
                    if write_output:
                        self.stderr.write(f'Row {row_number}: product/stock projection failed: {exc}')

            extended = self._build_extended_instance(
                row_data=row_data,
                header_specs=header_specs,
                source_file_name=source_file_name,
                source_date=source_date,
                row_number=row_number,
                row_hash=row_hash,
                batch_id=batch_id,
                product=product,
            )
            extended_rows.append(extended)

        if dry_run:
            stats['extended_skipped'] += len(extended_rows)
            return

        with transaction.atomic():
            created, updated = self._upsert_extended_rows(
                extended_rows, source_file_name, batch_id
            )
            stats['extended_created'] += created
            stats['extended_updated'] += updated

    def _upsert_product(self, row_data, dry_run):
        related_stats = {
            'brands_created': 0,
            'brands_updated': 0,
            'categories_created': 0,
            'categories_updated': 0,
        }
        vs_child_id = self._parse_field(Product._meta.get_field('vs_child_id'), row_data.get('VS Child ID'))
        if vs_child_id in self._seen_product_ids:
            raise ValueError(f'Duplicate VS Child ID {vs_child_id} in the file')
        self._seen_product_ids.add(vs_child_id)
        queryset = Product.all_objects if dry_run else Product.all_objects.select_for_update()
        product = queryset.filter(pk=vs_child_id).first()
        created = product is None
        if created:
            product = Product(vs_child_id=vs_child_id)

        defaults = {}
        for name, columns in PRODUCT_COLUMNS.items():
            columns = (columns,) if isinstance(columns, str) else columns
            column = next((column for column in columns if column in row_data), None)
            if column is None:
                continue
            value = row_data[column]
            if name in {'parent_product_title', 'child_product_title'} and not self._clean(value):
                value = getattr(product, name) or row_data.get('Parent Product Title')
                self._warning(f'{column} is blank; keeping the existing title or using Parent Product Title')
            if name == 'pick_location' and not self._clean(value) and not self.clear_blank_locations:
                continue
            defaults[name] = self._parse_field(Product._meta.get_field(name), value)

        for name in ('vs_parent_id', 'parent_product_title', 'child_product_title'):
            if created and name not in defaults:
                raise ValueError(f'Missing required product field: {PRODUCT_COLUMNS[name]}')
        for name in ('parent_reference', 'child_reference'):
            if name in defaults:
                defaults[name] = self._normalize_sku(defaults[name]) or ''
        if created and defaults.get('available_on_this_website') is not None:
            for name in ('child_active', 'parent_active'):
                defaults.setdefault(name, defaults['available_on_this_website'])

        brand = None
        if 'Brand' in row_data:
            brand, brand_created = self._get_brand(row_data['Brand'], dry_run)
            defaults['brand'] = brand
        if brand is not None:
            if brand_created:
                related_stats['brands_created'] += 1
            else:
                related_stats['brands_updated'] += 1
        fields = self._changed_fields(product, defaults, created)
        for name, value in defaults.items():
            setattr(product, name, value)
        if not dry_run:
            if created:
                product.save(force_insert=True)
            elif fields:
                product.save(update_fields=fields + ['updated_at'])
        if 'Categories' in row_data:
            category_stats, categories_changed = self._sync_categories(
                product, row_data['Categories'], dry_run=dry_run, created=created,
            )
            self._merge_stats(related_stats, category_stats)
            if categories_changed:
                fields.append('categories')
                if not dry_run and not created:
                    product.save(update_fields=['updated_at'])
        action = 'created' if created else ('updated' if fields else 'unchanged')
        return product, action, fields, related_stats

    def _upsert_stock_item(self, row_data, product, dry_run, batch_id):
        related_stats = {
            'colors_created': 0,
            'colors_updated': 0,
            'locations_created': 0,
            'locations_updated': 0,
        }
        sku = self._stock_sku(row_data, product)
        if not sku:
            raise ValueError('Cannot determine stock SKU')
        queryset = StockItem.all_objects if dry_run else StockItem.all_objects.select_for_update()
        stock_item = queryset.filter(pk=sku).first()
        if stock_item is not None and stock_item.product_id != product.pk:
            raise ValueError(f'Stock SKU {sku} is linked to a different product')
        created = stock_item is None
        if created:
            stock_item = StockItem(sku=sku, product=product)

        product_type = product.parent_reference or product.child_reference or sku
        product_type = self._normalize_sku(product_type)[:20]
        defaults = {
            'product': product,
            'is_active': product.is_active,
        }
        if created or any(key in row_data for key in ('Parent Reference', 'Child Reference', 'Child')):
            defaults['product_type'] = product_type
        has_color = any(self._clean(row_data.get(key)) for key in ('Tag 2 (Colours)', 'Attribute 2 (Colour)'))
        if created or has_color:
            color, color_created = self._get_or_create_color(row_data, dry_run)
            defaults['color'] = color
            related_stats['colors_created' if color_created else 'colors_updated'] += 1

        for name, column in (
            ('available_stock_in_mtr', 'Stock Value'),
            ('minimum_stock_level', 'Min Purchase Quantity'),
            ('maximum_stock_level', 'Max Purchase Quantity'),
            ('unit_cost', 'Cost Price (Inc VAT)'),
            ('last_purchase_price', 'Cost Price (Inc VAT)'),
        ):
            if column in row_data and self._clean(row_data[column]) is not None:
                defaults[name] = self._parse_field(StockItem._meta.get_field(name), row_data[column])

        location_name = self._clean(row_data.get('Pick Location'))
        if location_name or ('Pick Location' in row_data and self.clear_blank_locations):
            location, location_created = self._get_or_create_location(location_name, dry_run)
            if location is not None:
                related_stats['locations_created' if location_created else 'locations_updated'] += 1
            defaults['warehouse_location'] = self._parse_field(
                StockItem._meta.get_field('warehouse_location'), location_name,
            )
            defaults['primary_location'] = location

        old_stock = stock_item.available_stock_in_mtr
        fields = self._changed_fields(stock_item, defaults, created)
        for name, value in defaults.items():
            setattr(stock_item, name, value)
        if not dry_run:
            if created:
                stock_item.save(force_insert=True)
            elif fields:
                stock_item.save(update_fields=fields + ['updated_at', 'last_stock_update'])
            if 'available_stock_in_mtr' in fields and old_stock != stock_item.available_stock_in_mtr:
                StockMovement.objects.create(
                    stock_item=stock_item, movement_type='ADJUSTMENT',
                    quantity=stock_item.available_stock_in_mtr - old_stock,
                    old_stock_level=old_stock, new_stock_level=stock_item.available_stock_in_mtr,
                    reference_number=batch_id[:100], reason='Product backup import',
                    created_by='product-import',
                )
        action = 'created' if created else ('updated' if fields else 'unchanged')
        return stock_item, action, fields, related_stats

    def _sync_categories(self, product, categories_value, dry_run=False, created=False):
        stats = {'categories_created': 0, 'categories_updated': 0}
        names = self._category_names(categories_value)
        old_names = set() if created else set(product.categories.values_list('name', flat=True))
        changed = old_names != set(names)

        categories = []
        for name in names:
            category, category_created = self._related_object(Category, {'name': name}, {}, dry_run)
            stats['categories_created' if category_created else 'categories_updated'] += 1
            categories.append(category)
        if changed and not dry_run:
            product.categories.set(categories)
        return stats, changed

    def _get_brand(self, value, dry_run):
        name = self._clean(value)
        if not name:
            return None, False
        name = self._parse_field(Brand._meta.get_field('name'), name)
        return self._related_object(Brand, {'name': name}, {}, dry_run)

    def _get_or_create_color(self, row_data, dry_run):
        color_name = self._first_list_value(
            row_data.get('Tag 2 (Colours)')
            or row_data.get('Attribute 2 (Colour)')
        ) or 'Unknown'
        color_code = self._color_code(color_name)

        return self._related_object(
            Color, {'color_code': color_code}, {'color_name': color_name[:100]}, dry_run,
        )

    def _get_or_create_location(self, value, dry_run):
        name = self._clean(value)
        if not name:
            return None, False
        name = name[:100]
        return self._related_object(Location, {'name': name}, {}, dry_run)

    def _related_object(self, model, lookup, defaults, dry_run):
        key = (model, tuple(sorted(lookup.items())))
        for cache in (self._related_cache, self._pending_related):
            if key in cache:
                return cache[key], False
        manager = model._base_manager
        if dry_run:
            instance = manager.filter(**lookup).first()
            created = instance is None
            if created:
                instance = model(**lookup, **defaults)
        else:
            instance, created = manager.get_or_create(**lookup, defaults=defaults)
        self._pending_related[key] = instance
        return instance, created

    def _category_names(self, categories_value):
        names = []
        seen = set()
        for path in re.split(r'[,;]+', self._clean(categories_value) or ''):
            for part in path.split('>'):
                name = part.strip()
                if len(name) > 100:
                    raise ValueError('Category name exceeds 100 characters')
                key = name.lower()
                if name and key not in seen:
                    seen.add(key)
                    names.append(name)
        return names

    def _merge_stats(self, target, source):
        for key, value in source.items():
            if key in target:
                target[key] += value

    def _stock_sku(self, row_data, product=None):
        base_sku = (
            self._clean(row_data.get('Child Reference'))
            or self._clean(row_data.get('Parent Reference'))
            or self._clean(row_data.get('VS Child ID'))
        )
        return self._stock_sku_for_product(base_sku, product)

    def _stock_sku_for_product(self, base_sku, product=None):
        if not base_sku and product is not None:
            base_sku = f'VS{product.vs_child_id}'
        sku = self._normalize_sku(base_sku)[:50] if base_sku else None
        if not sku or product is None or not getattr(product, 'pk', None):
            return sku

        existing_for_product = StockItem.all_objects.filter(product_id=product.pk)
        linked_skus = list(existing_for_product.values_list('sku', flat=True)[:2])
        if linked_skus and existing_for_product.filter(pk=sku).exists():
            return sku

        suffix = f' {product.vs_child_id}'
        candidate = f'{sku[:50 - len(suffix)]}{suffix}'
        if linked_skus and existing_for_product.filter(pk=candidate).exists():
            return candidate

        # Keep a single legacy SKU only when the source reference is not owned
        # by another product. Never choose an arbitrary colour/roll stock row.
        if len(linked_skus) == 1 and not self._sku_conflicts(sku, product):
            return linked_skus[0]

        if not self._sku_conflicts(sku, product):
            if linked_skus:
                self._warning(
                    f'Product {product.pk}: existing stock links do not match the source reference. '
                    f'Using separate stock SKU {sku}; existing stock rows are preserved.'
                )
            return sku

        if not self._sku_conflicts(candidate, product):
            self._warning(
                f'Product {product.pk}: reference {sku} belongs to another product. '
                f'Using product-specific stock SKU {candidate}; no stock is relinked.'
            )
            return candidate

        fallback = f'VS{product.vs_child_id}'
        number = 1
        while self._sku_conflicts(fallback, product):
            fallback = f'VS{product.vs_child_id}-{number}'
            number += 1
        self._warning(
            f'Product {product.pk}: source SKU and product-specific SKU are occupied. '
            f'Using {fallback}; existing stock rows are preserved.'
        )
        return fallback

    def _sku_conflicts(self, sku, product):
        return (
            (sku in self._preview_stock_skus and self._preview_stock_skus[sku] != product.pk)
            or StockItem.all_objects.filter(sku=sku).exclude(product_id=product.pk).exists()
        )

    def _normalize_sku(self, value):
        return normalize_sku_reference(value)

    def _first_list_value(self, value):
        value = self._clean(value)
        if not value:
            return None
        for part in re.split(r'[\n,;/|]+', value):
            part = part.strip()
            if part:
                return part
        return None

    def _color_code(self, color_name):
        normalized = re.sub(r'[^A-Za-z0-9]+', '', color_name or '').upper()
        return (normalized[:10] or 'UNKNOWN')

    def _build_extended_instance(
        self, row_data, header_specs, source_file_name, source_date,
        row_number, row_hash, batch_id, product
    ):
        extended = ProductExtendedData(
            product=product if getattr(product, 'pk', None) else None,
            source_file_name=source_file_name,
            source_file_date=source_date,
            row_number=row_number,
            row_hash=row_hash,
            import_batch_id=batch_id,
            raw_data=row_data,
            raw_headers=header_specs,
            is_active=True,
        )

        field_by_db_column = {
            field.db_column or field.column: field.name
            for field in ProductExtendedData._meta.fields
            if field.name not in EXTENDED_METADATA_FIELDS
        }
        for db_column, value in row_data.items():
            field_name = field_by_db_column.get(db_column)
            if field_name:
                cleaned = self._clean(value)
                if field_name in {'parent_reference', 'child_reference', 'amazon_sku_uk'}:
                    cleaned = self._normalize_sku(cleaned)
                setattr(extended, field_name, cleaned)
        return extended

    def _upsert_extended_rows(self, extended_rows, source_file_name, batch_id):
        row_numbers = [row.row_number for row in extended_rows]
        row_hashes = [row.row_hash for row in extended_rows]
        existing_by_hash = {
            row.row_hash: row
            for row in ProductExtendedData.objects.filter(row_hash__in=row_hashes)
        }
        existing_by_batch_row = {
            row.row_number: row
            for row in ProductExtendedData.objects.filter(
                source_file_name=source_file_name,
                import_batch_id=batch_id,
                row_number__in=row_numbers,
            )
        }

        to_create = []
        to_update = []
        update_fields = [
            field.name
            for field in ProductExtendedData._meta.fields
            if field.name not in {'id', 'created_at', 'updated_at'}
        ]

        seen_hashes = set()
        for row in extended_rows:
            if row.row_hash in seen_hashes:
                continue
            seen_hashes.add(row.row_hash)

            current = existing_by_hash.get(row.row_hash) or existing_by_batch_row.get(row.row_number)
            if current is None:
                to_create.append(row)
                continue
            for field in update_fields:
                setattr(current, field, getattr(row, field))
            to_update.append(current)

        if to_create:
            ProductExtendedData.objects.bulk_create(to_create, batch_size=len(to_create))
        if to_update:
            ProductExtendedData.objects.bulk_update(
                to_update, update_fields, batch_size=max(1, len(to_update))
            )
        return len(to_create), len(to_update)

    def _build_header_specs(self, source_headers):
        specs = []
        seen = set()
        for index, header in enumerate(source_headers, start=1):
            original_header = str(header or '').strip()
            if original_header and original_header in seen:
                raise CommandError(f'Duplicate product column: {original_header}')
            seen.add(original_header)
            db_column = original_header or f'blank_column_{index}'
            specs.append({
                'index': index,
                'source_header': original_header,
                'db_column': db_column,
                'is_finalized': db_column in FINALIZED_COLUMNS,
            })
        return specs

    def _validate_extended_model_columns(self, header_specs):
        present_columns = {spec['db_column'] for spec in header_specs}
        missing = [
            column for column in ('VS Parent ID', 'VS Child ID')
            if column not in present_columns
        ]
        if missing:
            raise CommandError(
                'Product file is missing required identifier columns: '
                + ', '.join(missing)
            )

    def _row_data(self, header_specs, values):
        data = {}
        for offset, spec in enumerate(header_specs):
            data[spec['db_column']] = self._clean(values[offset]) if offset < len(values) else None
        return data

    def _row_hash(self, raw_payload):
        encoded = json.dumps(raw_payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def _source_date_from_name(self, file_name):
        match = re.search(r'(\d{8})', file_name)
        if not match:
            return None
        for date_format in ('%Y%m%d', '%d%m%Y'):
            try:
                return datetime.strptime(match.group(1), date_format).date()
            except ValueError:
                continue
        return None

    def _parse_field(self, field, value):
        value = self._clean(value)
        if value is None:
            if field.null:
                return None
            if field.has_default():
                return field.get_default()
            raise ValueError(f'{field.name} is required')
        try:
            if isinstance(field, models.BooleanField):
                parsed = self._to_bool(value)
                if parsed is None:
                    raise ValueError('expected Y/N, true/false, or 1/0')
            elif isinstance(field, models.IntegerField):
                decimal = Decimal(value)
                if not decimal.is_finite() or decimal != decimal.to_integral_value():
                    raise ValueError('expected a whole number')
                parsed = int(decimal)
            elif isinstance(field, models.DecimalField):
                parsed = Decimal(value)
                if not parsed.is_finite():
                    raise ValueError('expected a finite decimal')
                quantum = Decimal(1).scaleb(-field.decimal_places)
                rounded = parsed.quantize(quantum)
                if rounded != parsed:
                    raise ValueError(f'exceeds {field.decimal_places} decimal places')
                parsed = rounded
            elif isinstance(field, models.DateTimeField):
                # Visualsoft exports an unset date as a MySQL zero-date sentinel.
                if field.null and value in {'0000-00-00', '0000-00-00 00:00:00', '0000-00-00T00:00:00'}:
                    return None
                parsed = parse_datetime(value)
                if parsed is None:
                    date = parse_date(value)
                    parsed = datetime.combine(date, datetime.min.time()) if date else None
                if parsed is None:
                    raise ValueError('expected an ISO date or datetime')
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
            else:
                parsed = value
            relative_url = isinstance(field, models.URLField) and value.startswith('/') and not value.startswith('//')
            if relative_url:
                for validator in field.validators:
                    if not isinstance(validator, URLValidator):
                        validator(parsed)
            else:
                field.run_validators(parsed)
            return parsed
        except (ValidationError, InvalidOperation, ValueError, OverflowError) as exc:
            raise ValueError(f'{field.name}: {exc}') from exc

    def _changed_fields(self, instance, defaults, created):
        if created:
            return list(defaults)
        changed = []
        for name, value in defaults.items():
            field = instance._meta.get_field(name)
            current = getattr(instance, field.attname)
            expected = value.pk if isinstance(value, models.Model) else value
            new_relation = isinstance(value, models.Model) and value.pk is None
            if current != expected or new_relation:
                changed.append(name)
        return changed

    def _example(self, key, value):
        if len(self._stats[key]) < 20:
            self._stats[key].append(value)

    def _warning(self, message):
        self._stats['warnings'] += 1
        self._example('warning_examples', {'row_number': self._current_row, 'message': message})

    def _clean(self, value):
        if value is None:
            return None
        value = str(value).strip()
        return value if value else None

    def _to_int(self, value):
        value = self._clean(value)
        if value is None:
            return None
        try:
            return int(Decimal(value))
        except (InvalidOperation, ValueError):
            return None

    def _to_decimal(self, value):
        value = self._clean(value)
        if value is None:
            return None
        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    def _to_bool(self, value):
        value = self._clean(value)
        if value is None:
            return None
        normalized = value.lower()
        if normalized in {'y', 'yes', 'true', '1'}:
            return True
        if normalized in {'n', 'no', 'false', '0'}:
            return False
        return None

    def _active_flag(self, primary_value, fallback_value):
        parsed = self._to_bool(primary_value)
        if parsed is not None:
            return parsed
        fallback = self._to_bool(fallback_value)
        return fallback if fallback is not None else True
