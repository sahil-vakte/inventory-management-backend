from django.core.management.base import BaseCommand
from django.db import transaction

from stock.models import StockItem
from products.models import Product


class Command(BaseCommand):
    help = "Backfill StockItem.product by matching StockItem.product_type to Product fields"

    def handle(self, *args, **options):
        updated = 0
        skipped = 0

        with transaction.atomic():
            qs = StockItem.objects.filter(product__isnull=True)
            for s in qs:
                prod = None
                if s.product_type:
                    prod = Product.objects.filter(child_reference__iexact=s.product_type).first()
                    if not prod:
                        prod = Product.objects.filter(parent_reference__iexact=s.product_type).first()
                    if not prod:
                        # try numeric vs_child_id match
                        try:
                            vs_id = int(s.product_type)
                            prod = Product.objects.filter(vs_child_id=vs_id).first()
                        except Exception:
                            prod = None

                if prod:
                    s.product = prod
                    s.save(update_fields=['product'])
                    updated += 1
                else:
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Backfill completed. Updated: {updated}; Skipped: {skipped}"))
