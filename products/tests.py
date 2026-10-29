import csv
import io
import os
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook
from rest_framework.test import APIClient

from colors.models import Color
from products.management.commands.import_product_backup_csv import Command
from products.models import Brand, Category, Location, Product, ProductExtendedData
from stock.models import StockItem, StockMovement


class ProductCSVShortTitleImportTest(TestCase):
    def test_import_saves_short_title_on_product_and_extended_data(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', newline='', encoding='utf-8', delete=False
        ) as source_file:
            writer = csv.writer(source_file)
            writer.writerow([
                'VS Parent ID', 'VS Child ID', 'Parent Reference', 'Child Reference',
                'Parent Product Title', 'Child Product Title', 'ShortTitle',
            ])
            writer.writerow([
                '100', '101', 'PARENT-101', 'CHILD-101', 'Long Parent Name',
                'Long Child Name', 'Short Label Name',
            ])
            source_path = Path(source_file.name)

        try:
            Command().import_file(
                file_path=source_path,
                batch_id='short-title-import-test',
                chunk_size=1,
            )
        finally:
            os.unlink(source_path)

        product = Product.objects.get(vs_child_id=101)
        extended = ProductExtendedData.objects.get(import_batch_id='short-title-import-test')
        self.assertEqual(product.short_title, 'Short Label Name')
        self.assertEqual(extended.short_title, 'Short Label Name')
        self.assertEqual(extended.raw_data['ShortTitle'], 'Short Label Name')

    def test_import_accepts_windows_1252_csv(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', newline='', encoding='cp1252', delete=False
        ) as source_file:
            writer = csv.writer(source_file)
            writer.writerow([
                'VS Parent ID', 'VS Child ID', 'Parent Reference', 'Child Reference',
                'Parent Product Title', 'Child Product Title', 'ShortTitle',
            ])
            writer.writerow([
                '100', '102', 'PARENT-102', 'CHILD-102', 'Caf\xe9 Parent',
                'Caf\xe9 Child', 'Caf\xe9 Short Label',
            ])
            source_path = Path(source_file.name)

        try:
            Command().import_file(
                file_path=source_path,
                batch_id='windows-1252-import-test',
                chunk_size=1,
            )
        finally:
            os.unlink(source_path)

        product = Product.objects.get(vs_child_id=102)
        self.assertEqual(product.short_title, 'Caf\xe9 Short Label')


class ProductBackupWorkbookImportTest(TestCase):
    def workbook(self, rows, sheet='Products'):
        book = Workbook()
        worksheet = book.active
        worksheet.title = sheet
        headers = list(dict.fromkeys(key for row in rows for key in row))
        worksheet.append(headers)
        for row in rows:
            worksheet.append([row.get(key) for key in headers])
        content = io.BytesIO()
        book.save(content)
        book.close()
        return content.getvalue()

    def row(self, child=101, **values):
        row = {
            'VS Parent ID': 100, 'VS Child ID': child,
            'Parent Reference': 'PARENT', 'Child Reference': f'CHILD-{child}',
            'Parent Product Title': 'Long Parent Name',
            'Child Product Title': 'Long Child Name', 'ShortTitle': 'Short Label',
        }
        row.update(values)
        return row

    def import_rows(self, rows, sheet='Products', **options):
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as handle:
            path = Path(handle.name)
            handle.write(self.workbook(rows, sheet))
        self.addCleanup(os.unlink, path)
        return Command().import_file(path, batch_id='workbook-test', **options)

    def existing_product_and_stock(self):
        product = Product.objects.create(
            vs_child_id=101, vs_parent_id=100, parent_reference='PARENT',
            child_reference='CHILD-101', parent_product_title='Long Parent Name',
            child_product_title='Long Child Name', short_title='Old Short Label',
        )
        color = Color.objects.create(color_code='RED', color_name='Red')
        primary = Location.objects.create(name='Original Location')
        secondary = Location.objects.create(name='Backup Location')
        stock = StockItem.objects.create(
            sku='CHILD-101', product=product, product_type='PARENT', color=color,
            available_stock_in_mtr=10, reserved_stock=3, primary_location=primary,
            secondary_location=secondary, warehouse_location=primary.name,
        )
        return product, stock

    def test_dry_run_reports_changes_and_creates_nothing(self):
        product, stock = self.existing_product_and_stock()
        before = [model.objects.count() for model in (
            Product, StockItem, StockMovement, Location, Color, Brand, Category, ProductExtendedData,
        )]
        rows = [self.row(**{
            'Stock Value': 25, 'Pick Location': 'New Location',
            'Brand': 'New Brand', 'Categories': 'New Category', 'Tag 2 (Colours)': 'Blue',
        }), self.row(102)]

        stats = self.import_rows(rows, dry_run=True, chunk_size=1)

        self.assertEqual(stats['errors'], 0, stats['error_examples'])
        self.assertEqual(stats['products_created'], 1)
        self.assertEqual(stats['products_updated'], 1)
        self.assertEqual(stats['stock_created'], 1)
        self.assertEqual(stats['stock_updated'], 1)
        self.assertEqual(before, [model.objects.count() for model in (
            Product, StockItem, StockMovement, Location, Color, Brand, Category, ProductExtendedData,
        )])
        product.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(product.short_title, 'Old Short Label')
        self.assertEqual(stock.available_stock_in_mtr, 10)
        self.assertEqual(stock.primary_location.name, 'Original Location')

    def test_import_updates_stock_and_location_but_preserves_reservations_and_other_products(self):
        product, stock = self.existing_product_and_stock()
        secondary = stock.secondary_location_id
        absent = Product.objects.create(
            vs_child_id=999, vs_parent_id=999, parent_product_title='Keep', child_product_title='Keep',
        )
        rows = [self.row(**{'Stock Value': 25, 'Pick Location': 'New Location'}), self.row(102)]

        stats = self.import_rows(rows)

        self.assertEqual(stats['errors'], 0, stats['error_examples'])
        self.assertEqual(stats['products_created'], 1)
        self.assertEqual(stats['products_updated'], 1)
        self.assertTrue(Product.objects.filter(pk=absent.pk).exists())
        product.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(product.short_title, 'Short Label')
        self.assertEqual(stock.available_stock_in_mtr, 25)
        self.assertEqual(stock.reserved_stock, 3)
        self.assertEqual(stock.secondary_location_id, secondary)
        self.assertEqual(stock.primary_location.name, 'New Location')
        movement = StockMovement.objects.get(stock_item=stock)
        self.assertEqual((movement.old_stock_level, movement.new_stock_level, movement.quantity), (10, 25, 15))

        product_time, stock_time = product.updated_at, stock.updated_at
        preview = self.import_rows(rows, dry_run=True)
        repeated = self.import_rows(rows)
        self.assertEqual(preview['products_unchanged'], 2)
        self.assertEqual(repeated['products_unchanged'], 2)
        self.assertEqual(repeated['stock_unchanged'], 2)
        self.assertEqual(repeated['products_updated'], 0)
        product.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(product.updated_at, product_time)
        self.assertEqual(stock.updated_at, stock_time)
        self.assertEqual(StockMovement.objects.filter(stock_item=stock).count(), 1)

    def test_blank_location_preserved_unless_explicitly_cleared(self):
        product, stock = self.existing_product_and_stock()
        rows = [self.row(**{'Pick Location': None})]
        stats = self.import_rows(rows)
        self.assertEqual(stats['errors'], 0)
        stock.refresh_from_db()
        self.assertEqual(stock.primary_location.name, 'Original Location')
        self.import_rows(rows, clear_blank_locations=True)
        stock.refresh_from_db()
        self.assertIsNone(stock.primary_location_id)
        self.assertIsNone(stock.warehouse_location)

    def test_maps_all_model_fields_and_preserves_unmapped_columns_in_raw_data(self):
        row = self.row(**{
            'Attribute 2 (Colour)': 'Magenta', 'Attribute 8 (Width)': '150cm',
            'Attribute 9 (Size)': 'Large', 'Tag 4 (Trimmings)': 'Lace',
            'Tag 2 (Colours)': 'Red,' * 55, 'Tag 1 (Print/ Texture)': 'Printed,' * 30,
            'Deposit Price (Inc VAT)': '1.25', 'Featured': 'Y',
            'Minimum Age': 18, 'Available Now': 'Y', 'Trade Only Product': 'Y',
            'Release Date': datetime(2026, 10, 28, 12, 0), 'Archive (Delete)': 'Y',
            'Price Break 4 (Quantity)': 20, 'Price Break 4 (Price Inc VAT)': '2.50',
            'Amazon Title (UK)': 'Marketplace Title',
            'Child Product Url': '/fabrics/product-p101/s101',
        })
        stats = self.import_rows([row])
        self.assertEqual(stats['errors'], 0, stats['error_examples'])
        product = Product.objects.get(pk=101)
        self.assertEqual(product.attribute_colour, 'Magenta')
        self.assertEqual(product.attribute_width, '150cm')
        self.assertEqual(product.attribute_size, 'Large')
        self.assertEqual(product.tag_trimmings, 'Lace')
        self.assertEqual(product.tag_colours, 'Red,' * 55)
        self.assertEqual(product.deposit_price_inc_vat, Decimal('1.25'))
        self.assertTrue(product.featured)
        self.assertTrue(product.trade_only_product)
        self.assertTrue(product.available_now)
        self.assertEqual(product.minimum_age, 18)
        self.assertEqual(product.child_product_url, '/fabrics/product-p101/s101')
        self.assertEqual(product.release_date.year, 2026)
        self.assertEqual(product.price_break_4_price, Decimal('2.50'))
        self.assertTrue(product.archive_delete)
        self.assertFalse(product.is_deleted)
        self.assertEqual(ProductExtendedData.objects.get(product=product).raw_data['Amazon Title (UK)'], 'Marketplace Title')

    def test_missing_columns_preserve_values_and_present_blank_nullable_fields_clear(self):
        product, stock = self.existing_product_and_stock()
        product.product_subtitle = 'Old subtitle'
        product.save()
        row = {'VS Parent ID': 100, 'VS Child ID': 101, 'ShortTitle': 'New Short', 'Product Subtitle': None}
        stats = self.import_rows([row])
        self.assertEqual(stats['errors'], 0, stats['error_examples'])
        product.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(product.child_product_title, 'Long Child Name')
        self.assertIsNone(product.product_subtitle)
        self.assertEqual(stock.available_stock_in_mtr, 10)
        self.assertEqual(stats['stock_unchanged'], 1)

    def test_invalid_stock_rolls_back_product_and_does_not_block_later_rows(self):
        product, stock = self.existing_product_and_stock()
        stats = self.import_rows([
            self.row(**{'Stock Value': '2.5'}), self.row(102, **{'Stock Value': 12}),
        ])
        self.assertEqual(stats['errors'], 1)
        self.assertEqual(stats['products_created'], 1)
        product.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(product.short_title, 'Old Short Label')
        self.assertEqual(stock.available_stock_in_mtr, 10)
        self.assertTrue(Product.objects.filter(pk=102).exists())
        self.assertIn('whole number', stats['error_examples'][0]['error'])

    def test_duplicate_child_references_do_not_relink_stock(self):
        rows = [self.row(101, **{'Child Reference': 'SAME'}), self.row(102, **{'Child Reference': 'SAME'})]
        preview = self.import_rows(rows, dry_run=True)
        live = self.import_rows(rows)
        self.assertEqual(preview['errors'], 0, preview['error_examples'])
        self.assertEqual(live['errors'], 0, live['error_examples'])
        self.assertEqual(preview['stock_created'], live['stock_created'])
        self.assertEqual(StockItem.objects.get(pk='SAME').product_id, 101)
        self.assertEqual(StockItem.objects.get(pk='SAME 102').product_id, 102)

    def test_multiple_stock_items_require_an_exact_reference_match(self):
        product, stock = self.existing_product_and_stock()
        alternate = StockItem.objects.create(
            sku='ALTERNATE', product=product, product_type='PARENT', color=stock.color,
            available_stock_in_mtr=99,
        )
        stats = self.import_rows([self.row(**{'Stock Value': 12})])
        self.assertEqual(stats['errors'], 0, stats['error_examples'])
        stock.refresh_from_db()
        alternate.refresh_from_db()
        self.assertEqual(stock.available_stock_in_mtr, 12)
        self.assertEqual(alternate.available_stock_in_mtr, 99)
        invalid = self.import_rows([self.row(**{'Child Reference': 'UNKNOWN'})], dry_run=True)
        self.assertEqual(invalid['errors'], 1)
        self.assertIn('multiple stock items', invalid['error_examples'][0]['error'])

    def test_zero_stock_is_applied_without_deleting_or_restoring_products(self):
        product, stock = self.existing_product_and_stock()
        product.soft_delete()
        stock.soft_delete()
        stats = self.import_rows([self.row(**{'Stock Value': 0, 'VAT Rate': 0})])
        self.assertEqual(stats['errors'], 0, stats['error_examples'])
        product.refresh_from_db()
        stock.refresh_from_db()
        self.assertTrue(product.is_deleted)
        self.assertTrue(stock.is_deleted)
        self.assertEqual(product.vat_rate, Decimal('0.00'))
        self.assertEqual(stock.available_stock_in_mtr, 0)
        self.assertEqual(stock.reserved_stock, 3)

    def test_oversized_and_invalid_values_are_reported_in_dry_run(self):
        stats = self.import_rows([
            self.row(**{'ShortTitle': 'X' * 501}),
            self.row(102, **{'Child Active': 'perhaps'}),
            self.row(103, **{'VS Child ID': '103.5'}),
        ], dry_run=True)
        self.assertEqual(stats['errors'], 3)
        self.assertFalse(Product.all_objects.exists())

    def test_blank_child_title_uses_parent_title_and_warns(self):
        stats = self.import_rows([self.row(**{
            'Child Product Title': None, 'Release Date': '0000-00-00 00:00:00',
        })])
        self.assertEqual(stats['errors'], 0, stats['error_examples'])
        self.assertEqual(stats['warnings'], 1)
        self.assertEqual(Product.objects.get(pk=101).child_product_title, 'Long Parent Name')
        self.assertIsNone(Product.objects.get(pk=101).release_date)

    def test_legacy_sheet_supported_and_duplicate_ids_reported(self):
        stats = self.import_rows([self.row(), self.row()], sheet='Product Master', dry_run=True)
        self.assertEqual(stats['products_created'], 1)
        self.assertEqual(stats['errors'], 1)
        self.assertIn('Duplicate VS Child ID', stats['error_examples'][0]['error'])

    def test_upload_api_supports_excel_dry_run_and_live_import(self):
        user = get_user_model().objects.create_user(username='product-import-test', password='test-only')
        client = APIClient()
        client.force_authenticate(user=user)
        for dry_run in ('true', 'false'):
            upload = SimpleUploadedFile('backup.xlsx', self.workbook([self.row()]))
            response = client.post('/api/v1/products/import-excel/', {
                'file': upload, 'dry_run': dry_run, 'sync': 'true',
            }, format='multipart')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertFalse(response.data['has_errors'])
            self.assertEqual(response.data['stats']['products_created'], 1)
            self.assertEqual(Product.objects.count(), 0 if dry_run == 'true' else 1)
