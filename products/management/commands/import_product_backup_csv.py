import csv
import hashlib
import json
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from products.models import Brand, Category, Product, ProductExtendedData

logger = logging.getLogger(__name__)


FINALIZED_COLUMNS = {
    'VS Parent ID',
    'VS Child ID',
    'Parent Reference',
    'Available On This Website',
    'Parent Product Title',
    'Child Product Title',
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


class Command(BaseCommand):
    help = (
        'Import the full Actual_Product_Data backup CSV into ProductExtendedData '
        'and project finalized columns into Product without changing existing APIs.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to Actual_Product_Data_BackUp CSV')
        parser.add_argument('--batch-id', default=None, help='Import batch identifier')
        parser.add_argument('--chunk-size', type=int, default=500, help='Rows to process per transaction')
        parser.add_argument('--limit', type=int, default=None, help='Optional maximum number of data rows to read')
        parser.add_argument('--dry-run', action='store_true', help='Validate and report without writing')
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
            write_output=True,
        )

        self.stdout.write(self.style.SUCCESS('Import scan complete.'))
        for key, value in stats.items():
            self.stdout.write(f'{key}: {value}')

    def import_file(
        self, file_path, batch_id=None, chunk_size=500, limit=None,
        dry_run=False, skip_products=False, write_output=False
    ):
        file_path = Path(file_path)
        if not file_path.exists():
            raise CommandError(f'File not found: {file_path}')

        batch_id = batch_id or timezone.now().strftime('%Y%m%d%H%M%S')
        chunk_size = max(1, chunk_size)
        source_date = self._source_date_from_name(file_path.name)

        stats = {
            'rows_seen': 0,
            'products_created': 0,
            'products_updated': 0,
            'extended_created': 0,
            'extended_updated': 0,
            'extended_skipped': 0,
            'invalid_product_rows': 0,
            'errors': 0,
        }

        if write_output:
            self.stdout.write(
                f"Importing {file_path.name} with batch '{batch_id}'"
                + (' (dry run)' if dry_run else '')
            )

        with file_path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.reader(handle)
            try:
                source_headers = next(reader)
            except StopIteration:
                raise CommandError('CSV file is empty')

            header_specs = self._build_header_specs(source_headers)
            self._validate_extended_model_columns(header_specs)

            chunk = []
            for row_number, values in enumerate(reader, start=2):
                if limit is not None and stats['rows_seen'] >= limit:
                    break
                stats['rows_seen'] += 1
                chunk.append((row_number, values))
                if len(chunk) >= chunk_size:
                    self._process_chunk(
                        chunk, header_specs, file_path.name, source_date,
                        batch_id, dry_run, skip_products, stats, write_output
                    )
                    chunk = []

            if chunk:
                self._process_chunk(
                    chunk, header_specs, file_path.name, source_date,
                    batch_id, dry_run, skip_products, stats, write_output
                )

        return stats

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
                    product, created = self._upsert_product(row_data, dry_run)
                    if product is None:
                        stats['invalid_product_rows'] += 1
                    elif created:
                        stats['products_created'] += 1
                    else:
                        stats['products_updated'] += 1
                except Exception as exc:
                    stats['errors'] += 1
                    logger.exception('Could not project product row %s', row_number)
                    if write_output:
                        self.stderr.write(f'Row {row_number}: product projection failed: {exc}')

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
        vs_child_id = self._to_int(row_data.get('VS Child ID'))
        if vs_child_id is None:
            return None, False

        vs_parent_id = self._to_int(row_data.get('VS Parent ID')) or 0
        brand = self._get_brand(row_data.get('Brand'), dry_run)
        defaults = {
            'vs_parent_id': vs_parent_id,
            'parent_reference': self._clean(row_data.get('Parent Reference')) or '',
            'child_reference': self._clean(row_data.get('Child Reference')) or '',
            'parent_product_title': self._clean(row_data.get('Parent Product Title')) or '',
            'child_product_title': self._clean(row_data.get('Child Product Title')) or '',
            'product_subtitle': self._clean(row_data.get('Product Subtitle')),
            'product_summary': self._clean(row_data.get('Product Summary')),
            'product_description': self._clean(row_data.get('Product Description')),
            'brand': brand,
            'available_on_this_website': self._to_bool(row_data.get('Available On This Website')),
            'attribute_length': self._clean(row_data.get('Attribute 1 (Length)')),
            'tag_colours': self._clean(row_data.get('Tag 2 (Colours)')),
            'tag_material': self._clean(row_data.get('Tag 3 (Material)')),
            'tag_print_texture': self._clean(row_data.get('Tag 1 (Print/ Texture)')),
            'allow_sample_request': self._to_bool(row_data.get('Allow Sample Request')),
            'sample_request_cost': self._to_decimal(row_data.get('Sample Request Cost')),
            'parent_product_sash': self._clean(row_data.get('Parent Product Sash')),
            'rrp_price_inc_vat': self._to_decimal(row_data.get('RRP Price (Inc VAT)')) or Decimal('0.00'),
            'cost_price_inc_vat': self._to_decimal(row_data.get('Cost Price (Inc VAT)')) or Decimal('0.00'),
            'vat_rate': self._to_decimal(row_data.get('VAT Rate')) or Decimal('20.00'),
            'display_on_sale_page': self._to_bool(row_data.get('Display On Sale Page')) is not False,
            'stock_value': self._to_decimal(row_data.get('Stock Value')) or Decimal('0.00'),
            'weight_kg': self._to_decimal(row_data.get('Weight (in KGs)')) or Decimal('0.000'),
            'parent_product_url': self._clean(row_data.get('Parent Product Url')),
            'child_product_url': self._clean(row_data.get('Child Product Url')),
            'parent_product_images': self._clean(row_data.get('Parent Product Images')),
            'child_product_images': self._clean(row_data.get('Child Product Images')),
            'meta_title': self._clean(row_data.get('Meta Title')),
            'meta_keywords': self._clean(row_data.get('Meta Keywords')),
            'meta_description': self._clean(row_data.get('Meta Description')),
        }

        for number in range(1, 6):
            defaults[f'price_break_{number}_quantity'] = self._to_int(
                row_data.get(f'Price Break {number} (Quantity)')
            )
            defaults[f'price_break_{number}_price'] = self._to_decimal(
                row_data.get(f'Price Break {number} (Price Inc VAT)')
            )
            defaults[f'price_break_{number}_sale_price'] = self._to_decimal(
                row_data.get(f'Price Break {number} (Sale Price Inc VAT)')
            )
            defaults[f'price_break_{number}_deposit_price'] = self._to_decimal(
                row_data.get(f'Price Break {number} (Deposit Price Inc VAT)')
            )
            defaults[f'price_break_{number}_allow_further_discounts'] = self._to_bool(
                row_data.get(f'Price Break {number} (Allow Further Discounts Inc VAT)')
            )

        if dry_run:
            existing = Product.all_objects.filter(vs_child_id=vs_child_id).exists()
            product = Product(vs_child_id=vs_child_id, **defaults)
            return product, not existing

        product, created = Product.all_objects.update_or_create(
            vs_child_id=vs_child_id,
            defaults=defaults,
        )
        self._sync_categories(product, row_data.get('Categories'))
        return product, created

    def _sync_categories(self, product, categories_value):
        names = [
            part.strip()
            for part in re.split(r'[>|,/;]+', self._clean(categories_value) or '')
            if part.strip()
        ]
        if not names:
            return

        categories = []
        for name in names:
            category, _ = Category.all_objects.get_or_create(name=name[:100])
            categories.append(category)
        product.categories.set(categories)

    def _get_brand(self, value, dry_run):
        name = self._clean(value)
        if not name:
            return None
        if dry_run:
            return Brand(name=name[:100])
        brand, _ = Brand.all_objects.get_or_create(name=name[:100])
        return brand

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
                setattr(extended, field_name, self._clean(value))
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
        for index, header in enumerate(source_headers, start=1):
            original_header = (header or '').strip()
            db_column = original_header or f'blank_column_{index}'
            specs.append({
                'index': index,
                'source_header': original_header,
                'db_column': db_column,
                'is_finalized': db_column in FINALIZED_COLUMNS,
            })
        return specs

    def _validate_extended_model_columns(self, header_specs):
        model_db_columns = {
            field.db_column or field.column
            for field in ProductExtendedData._meta.fields
            if field.name not in EXTENDED_METADATA_FIELDS
        }
        missing = [
            spec['db_column']
            for spec in header_specs
            if spec['db_column'] not in model_db_columns
        ]
        if missing:
            raise CommandError(
                'ProductExtendedData is missing CSV columns: '
                + ', '.join(missing[:10])
            )

    def _row_data(self, header_specs, values):
        data = {}
        for offset, spec in enumerate(header_specs):
            data[spec['db_column']] = values[offset] if offset < len(values) else ''
        return data

    def _row_hash(self, raw_payload):
        encoded = json.dumps(raw_payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def _source_date_from_name(self, file_name):
        match = re.search(r'(\d{8})', file_name)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), '%d%m%Y').date()
        except ValueError:
            return None

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
