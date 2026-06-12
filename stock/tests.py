from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from colors.models import Color
from products.models import Product
from stock.models import StockBatch, StockBatchRoll, StockItem, StockMovement


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
