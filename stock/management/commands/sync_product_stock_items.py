from django.core.management.base import BaseCommand
from django.db import transaction

from stock.services.product_stock_sync import sync_product_stock_items


class Command(BaseCommand):
    help = 'Create/update stock rows so every product has a stock item.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be created/updated without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        with transaction.atomic():
            stats = sync_product_stock_items(dry_run=dry_run)
            if dry_run:
                transaction.set_rollback(True)

        mode = 'Dry run complete' if dry_run else 'Product stock sync complete'
        self.stdout.write(self.style.SUCCESS(mode))
        for key, value in stats.items():
            self.stdout.write(f'{key}: {value}')
