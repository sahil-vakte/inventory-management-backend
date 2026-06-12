from django.core.management.base import BaseCommand, CommandError

from orders.services.remote_tiaknight_import import (
    RemoteTiaknightConfigError,
    RemoteTiaknightFetchError,
    RemoteTiaknightParseError,
    import_remote_tiaknight_orders,
)


class Command(BaseCommand):
    help = 'Import orders from the remote Tiaknight SOAP service.'

    def handle(self, *args, **options):
        try:
            result = import_remote_tiaknight_orders(user=None)
        except (
            RemoteTiaknightConfigError,
            RemoteTiaknightFetchError,
            RemoteTiaknightParseError,
            ValueError,
        ) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('Remote Tiaknight import complete.'))
        self.stdout.write(f"orders_created: {result['created_count']}")
        self.stdout.write(f"orders_failed: {result['failed_count']}")
        if result['errors']:
            self.stdout.write('errors:')
            for error in result['errors'][:10]:
                self.stdout.write(f'  {error}')
