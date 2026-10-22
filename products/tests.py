import csv
import os
import tempfile
from pathlib import Path

from django.test import TestCase

from products.management.commands.import_product_backup_csv import Command
from products.models import Product, ProductExtendedData


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
