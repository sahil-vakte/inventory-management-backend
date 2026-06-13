from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from colors.models import Color
from products.models import Product
from stock.models import StockBatch, StockBatchRoll, StockItem, StockMovement
from stock.services.product_stock_sync import sync_product_stock_items


class StockBatchIncomingAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='warehouse', password='test123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.color = Color.objects.create(color_code='BLK', color_name='Black')
        self.product = Product.objects.create(
            vs_parent_id=1,
            vs_child_id=1,
            parent_reference='AB',
            child_reference='AB',
            parent_product_title='Product AB',
            child_product_title='Product AB',
            rrp_price_inc_vat=Decimal('10.00'),
            cost_price_inc_vat=Decimal('5.00'),
        )
        self.stock_item = StockItem.objects.create(
            sku='AB',
            product_type='FABRIC',
            product=self.product,
            color=self.color,
            available_stock_in_mtr=50,
        )

    def test_create_incoming_batch_updates_stock_and_logs_movement(self):
        response = self.client.post(
            '/api/v1/stock-batches/',
            {
                'sku': 'AB',
                'supplier': 'Supplier Ltd',
                'rolls': [
                    {'roll_number': 1, 'meterage': 100},
                    {'roll_number': 2, 'meterage': 50},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.available_stock_in_mtr, 200)

        batch = StockBatch.objects.get(batch_id=response.data['batch_id'])
        self.assertEqual(batch.total_meterage, 150)
        self.assertEqual(batch.roll_count, 2)
        self.assertEqual(batch.created_by, self.user)
        self.assertEqual(batch.rolls.count(), 2)

        movement = StockMovement.objects.get(reference_number=batch.batch_id)
        self.assertEqual(movement.movement_type, 'IN')
        self.assertEqual(movement.quantity, 150)
        self.assertEqual(movement.old_stock_level, 50)
        self.assertEqual(movement.new_stock_level, 200)
        self.assertEqual(movement.created_by, self.user.username)

        self.assertEqual(response.data['old_stock_in_mtr'], 50)
        self.assertEqual(response.data['incoming_meterage'], 150)
        self.assertEqual(response.data['new_stock_in_mtr'], 200)

    def test_label_endpoint_returns_one_label_per_roll(self):
        batch = StockBatch.objects.create(
            stock_item=self.stock_item,
            sku='AB',
            product_name='Product AB',
            supplier='Supplier Ltd',
            created_by=self.user,
            total_meterage=150,
            roll_count=2,
        )
        StockBatchRoll.objects.create(batch=batch, roll_number=1, meterage=100)
        StockBatchRoll.objects.create(batch=batch, roll_number=2, meterage=50)

        response = self.client.get(f'/api/v1/stock-batches/{batch.batch_id}/labels/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['batch_id'], batch.batch_id)
        self.assertEqual(len(response.data['labels']), 2)
        self.assertEqual(response.data['labels'][0]['sku'], 'AB')
        self.assertEqual(response.data['labels'][0]['product_name'], 'Product AB')
        self.assertEqual(response.data['labels'][0]['meterage'], 100)
        self.assertEqual(response.data['labels'][0]['supplier'], 'Supplier Ltd')

    def test_mark_labels_generated_updates_rolls(self):
        batch = StockBatch.objects.create(
            stock_item=self.stock_item,
            sku='AB',
            product_name='Product AB',
            supplier='Supplier Ltd',
            created_by=self.user,
            total_meterage=100,
            roll_count=1,
        )
        roll = StockBatchRoll.objects.create(batch=batch, roll_number=1, meterage=100)

        response = self.client.post(
            f'/api/v1/stock-batches/{batch.batch_id}/mark-labels-generated/',
            {},
        )

        self.assertEqual(response.status_code, 200)
        roll.refresh_from_db()
        self.assertTrue(roll.label_generated)
        self.assertIsNotNone(roll.label_generated_at)
        self.assertEqual(roll.label_generated_by, self.user)

    def test_create_rejects_duplicate_roll_numbers_without_stock_change(self):
        response = self.client.post(
            '/api/v1/stock-batches/',
            {
                'sku': 'AB',
                'supplier': 'Supplier Ltd',
                'rolls': [
                    {'roll_number': 1, 'meterage': 100},
                    {'roll_number': 1, 'meterage': 50},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.available_stock_in_mtr, 50)
        self.assertEqual(StockBatch.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_create_rejects_unknown_sku(self):
        response = self.client.post(
            '/api/v1/stock-batches/',
            {
                'sku': 'MISSING',
                'supplier': 'Supplier Ltd',
                'rolls': [{'roll_number': 1, 'meterage': 100}],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('sku', response.data)

    def test_create_normalizes_parenthesized_sku_for_batch_and_labels(self):
        StockItem.objects.create(
            sku='(109 LT) DSND',
            product_type='FABRIC',
            product=self.product,
            color=self.color,
            available_stock_in_mtr=10,
        )

        response = self.client.post(
            '/api/v1/stock-batches/',
            {
                'sku': '109 LT DSND',
                'supplier': 'Supplier Ltd',
                'rolls': [{'roll_number': 1, 'meterage': 25}],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['sku'], '109 LT DSND')
        batch = StockBatch.objects.get(batch_id=response.data['batch_id'])
        self.assertEqual(batch.sku, '109 LT DSND')
        self.assertEqual(batch.stock_item.sku, '109 LT DSND')
        batch.stock_item.refresh_from_db()
        self.assertEqual(batch.stock_item.available_stock_in_mtr, 35)

        label_response = self.client.get(f'/api/v1/stock-batches/{batch.batch_id}/labels/')
        self.assertEqual(label_response.status_code, 200)
        self.assertEqual(label_response.data['labels'][0]['sku'], '109 LT DSND')


class ProductStockSyncTest(TestCase):
    def setUp(self):
        self.color = Color.objects.create(color_code='BLK', color_name='Black')

    def test_sync_creates_zero_stock_for_product_without_stock(self):
        product = Product.objects.create(
            vs_parent_id=200,
            vs_child_id=200,
            parent_reference='Q1249 LMN',
            child_reference='Q1249 LMN',
            parent_product_title='Parent Product',
            child_product_title='Child Product',
        )

        stats = sync_product_stock_items()

        self.assertEqual(stats['stock_created'], 1)
        stock = StockItem.all_objects.get(product=product)
        self.assertEqual(stock.sku, 'Q1249 LMN')
        self.assertEqual(stock.available_stock_in_mtr, 0)
        self.assertTrue(stock.is_active)

    def test_sync_uses_unique_fallback_sku_for_duplicate_product_reference(self):
        first = Product.objects.create(
            vs_parent_id=300,
            vs_child_id=300,
            parent_reference='DUP SKU',
            child_reference='DUP SKU',
            parent_product_title='First Parent',
            child_product_title='First Child',
        )
        second = Product.objects.create(
            vs_parent_id=301,
            vs_child_id=301,
            parent_reference='DUP SKU',
            child_reference='DUP SKU',
            parent_product_title='Second Parent',
            child_product_title='Second Child',
        )

        sync_product_stock_items()

        self.assertTrue(StockItem.all_objects.filter(product=first, sku='DUP SKU').exists())
        self.assertTrue(StockItem.all_objects.filter(product=second, sku='DUP SKU 301').exists())

    def test_sync_keeps_stock_inactive_when_product_is_inactive(self):
        product = Product.objects.create(
            vs_parent_id=400,
            vs_child_id=400,
            parent_reference='INACTIVE SKU',
            child_reference='INACTIVE SKU',
            parent_product_title='Inactive Parent',
            child_product_title='Inactive Child',
            child_active=False,
            parent_active=False,
        )
        StockItem.objects.create(
            sku='INACTIVE SKU',
            product_type='INACTIVE SKU',
            product=product,
            color=self.color,
            available_stock_in_mtr=10,
            is_active=True,
        )

        sync_product_stock_items()

        stock = StockItem.all_objects.get(product=product)
        self.assertFalse(stock.is_active)
