from stock.management.commands.normalize_stock_skus import Command as NormalizeStockSkusCommand


class Command(NormalizeStockSkusCommand):
    help = "Compatibility alias for normalize_stock_skus."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Alias for the default dry-run mode.',
        )

    def handle(self, *args, **options):
        if options.pop('dry_run', False):
            options['commit'] = False
        return super().handle(*args, **options)
