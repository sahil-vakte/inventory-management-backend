from django.core.management.base import BaseCommand
from django.db import connection, transaction

from orders.models import OrderItem
from products.models import Product, ProductExtendedData
from stock.models import StockBatch, StockItem, StockMovement
from stock.sku_utils import normalize_sku_reference


class Command(BaseCommand):
    help = "Normalize product/stock/order SKUs from '(109 LT) DSND' to '109 LT DSND'."

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Apply changes. Without this flag, the command only reports what would change.',
        )

    def handle(self, *args, **options):
        commit = options['commit']
        stats = {
            'products_updated': 0,
            'stock_renamed': 0,
            'stock_merged': 0,
            'stock_product_type_updated': 0,
            'stock_batches_updated': 0,
            'stock_movements_relinked': 0,
            'order_items_relinked': 0,
            'order_item_skus_updated': 0,
            'order_item_product_types_updated': 0,
            'extended_product_rows_updated': 0,
        }

        with transaction.atomic():
            constraints_disabled = connection.disable_constraint_checking()
            try:
                self._normalize_products(commit, stats)
                self._normalize_product_extended_data(commit, stats)
                self._normalize_stock_items(commit, stats)
                self._normalize_remaining_rows(commit, stats)
            finally:
                if constraints_disabled:
                    connection.enable_constraint_checking()
                    connection.check_constraints()

            if not commit:
                transaction.set_rollback(True)

        mode = 'Applied' if commit else 'Dry run'
        self.stdout.write(self.style.SUCCESS(f'{mode} SKU normalization complete.'))
        for key, value in stats.items():
            self.stdout.write(f'{key}: {value}')

        if not commit:
            self.stdout.write(self.style.WARNING('No data was changed. Re-run with --commit to apply.'))

    def _normalize_products(self, commit, stats):
        for product in Product.all_objects.all().iterator():
            updates = {}
            for field in ('parent_reference', 'child_reference'):
                current = getattr(product, field)
                normalized = normalize_sku_reference(current)
                if normalized != (current or ''):
                    updates[field] = normalized

            if not updates:
                continue

            stats['products_updated'] += 1
            if commit:
                Product.all_objects.filter(pk=product.pk).update(**updates)

    def _normalize_product_extended_data(self, commit, stats):
        sku_fields = (
            'parent_reference',
            'child_reference',
            'amazon_sku_uk',
        )
        for row in ProductExtendedData.objects.all().iterator():
            updates = {}
            for field in sku_fields:
                current = getattr(row, field, None)
                normalized = normalize_sku_reference(current)
                if normalized != (current or ''):
                    updates[field] = normalized

            if not updates:
                continue

            stats['extended_product_rows_updated'] += 1
            if commit:
                ProductExtendedData.objects.filter(pk=row.pk).update(**updates)

    def _normalize_stock_items(self, commit, stats):
        stock_items = list(StockItem.all_objects.all().order_by('sku'))

        for source in stock_items:
            old_sku = source.sku
            new_sku = normalize_sku_reference(old_sku)
            normalized_type = normalize_sku_reference(source.product_type)[:20]

            if not new_sku or new_sku == old_sku:
                if normalized_type != source.product_type:
                    stats['stock_product_type_updated'] += 1
                    if commit:
                        StockItem.all_objects.filter(pk=old_sku).update(product_type=normalized_type)
                continue

            target = StockItem.all_objects.filter(sku=new_sku).first()
            if target:
                stats['stock_merged'] += 1
                movement_count, batch_count, linked_order_count, sku_order_count = (
                    self._related_counts(old_sku)
                )
                stats['stock_movements_relinked'] += movement_count
                stats['stock_batches_updated'] += batch_count
                stats['order_items_relinked'] += linked_order_count
                stats['order_item_skus_updated'] += sku_order_count
                if commit:
                    self._merge_stock_item(target, source)
                    self._update_related_stock_references(old_sku, new_sku)
                    StockItem.all_objects.filter(pk=old_sku).delete()
                continue

            movement_count, batch_count, linked_order_count, sku_order_count = self._related_counts(old_sku)
            stats['stock_renamed'] += 1
            stats['stock_movements_relinked'] += movement_count
            stats['stock_batches_updated'] += batch_count
            stats['order_items_relinked'] += linked_order_count
            stats['order_item_skus_updated'] += sku_order_count
            if commit:
                self._update_related_stock_references(old_sku, new_sku)
                StockItem.all_objects.filter(pk=old_sku).update(
                    sku=new_sku,
                    product_type=normalized_type,
                )

    def _normalize_remaining_rows(self, commit, stats):
        for stock_item in StockItem.all_objects.all().iterator():
            normalized_type = normalize_sku_reference(stock_item.product_type)[:20]
            if normalized_type and normalized_type != stock_item.product_type:
                stats['stock_product_type_updated'] += 1
                if commit:
                    StockItem.all_objects.filter(pk=stock_item.pk).update(product_type=normalized_type)

        for batch in StockBatch.all_objects.all().iterator():
            normalized_sku = normalize_sku_reference(batch.sku)
            if normalized_sku != batch.sku:
                stats['stock_batches_updated'] += 1
                if commit:
                    StockBatch.all_objects.filter(pk=batch.pk).update(sku=normalized_sku)

        for item in OrderItem.objects.all().iterator():
            normalized_sku = normalize_sku_reference(item.sku)[:50]
            normalized_type = normalize_sku_reference(item.product_type)[:50]
            updates = {}
            if normalized_sku != item.sku:
                stats['order_item_skus_updated'] += 1
                updates['sku'] = normalized_sku
            if normalized_type != (item.product_type or ''):
                stats['order_item_product_types_updated'] += 1
                updates['product_type'] = normalized_type
            if updates and commit:
                OrderItem.objects.filter(pk=item.pk).update(**updates)

    def _related_counts(self, old_sku):
        return (
            StockMovement.all_objects.filter(stock_item_id=old_sku).count(),
            StockBatch.all_objects.filter(stock_item_id=old_sku).count()
            + StockBatch.all_objects.filter(sku=old_sku).count(),
            OrderItem.objects.filter(stock_item_id=old_sku).count(),
            OrderItem.objects.filter(sku=old_sku).count(),
        )

    def _update_related_stock_references(self, old_sku, new_sku):
        StockMovement.all_objects.filter(stock_item_id=old_sku).update(stock_item_id=new_sku)
        StockBatch.all_objects.filter(stock_item_id=old_sku).update(stock_item_id=new_sku)
        StockBatch.all_objects.filter(sku=old_sku).update(sku=new_sku)
        OrderItem.objects.filter(stock_item_id=old_sku).update(stock_item_id=new_sku)
        OrderItem.objects.filter(sku=old_sku).update(sku=new_sku)

    def _merge_stock_item(self, target, source):
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

        target.product_type = normalize_sku_reference(target.product_type)[:20]
        target.is_active = target.is_active or source.is_active
        target.is_discontinued = target.is_discontinued and source.is_discontinued
        target.is_deleted = target.is_deleted and source.is_deleted
        if not target.deleted_at and source.deleted_at:
            target.deleted_at = source.deleted_at
        target.save()
