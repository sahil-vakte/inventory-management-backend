from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from orders.services.remote_tiaknight_import import (
    RemoteTiaknightConfigError,
    RemoteTiaknightFetchError,
    RemoteTiaknightParseError,
    import_remote_tiaknight_orders,
)


class Command(BaseCommand):
    help = 'Import orders from the remote Tiaknight SOAP service.'

    def handle(self, *args, **options):
        started_at = timezone.localtime()
        self.stdout.write(f"[{started_at:%Y-%m-%d %H:%M:%S %Z}] Remote Tiaknight import started.")

        try:
            result = import_remote_tiaknight_orders(user=None)
        except (
            RemoteTiaknightConfigError,
            RemoteTiaknightFetchError,
            RemoteTiaknightParseError,
            ValueError,
        ) as exc:
            failed_at = timezone.localtime()
            self.stderr.write(f"[{failed_at:%Y-%m-%d %H:%M:%S %Z}] Remote Tiaknight import failed: {exc}")
            raise CommandError(str(exc)) from exc

        completed_at = timezone.localtime()
        self.stdout.write(self.style.SUCCESS(
            f"[{completed_at:%Y-%m-%d %H:%M:%S %Z}] Remote Tiaknight import complete."
        ))
        self.stdout.write(f"[{completed_at:%Y-%m-%d %H:%M:%S %Z}] orders_created: {result['created_count']}")
        self.stdout.write(f"[{completed_at:%Y-%m-%d %H:%M:%S %Z}] orders_failed: {result['failed_count']}")
        if result['errors']:
            self.stdout.write(f'[{completed_at:%Y-%m-%d %H:%M:%S %Z}] errors:')
            for error in result['errors'][:10]:
                self.stdout.write(f'  {error}')
