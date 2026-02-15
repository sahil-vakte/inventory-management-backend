"""
Django management command to sync eBay orders to the database.

Usage:
    python manage.py sync_ebay_orders
    python manage.py sync_ebay_orders --days=7
    python manage.py sync_ebay_orders --status=Active
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from orders.services.ebay_service import EbayService
from orders.ebay_config import EbayConfig
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync orders from eBay to the database'
    
    def add_arguments(self, parser):
        """Add command line arguments"""
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Number of days to look back for orders (default: from config)'
        )
        
        parser.add_argument(
            '--status',
            type=str,
            default='All',
            choices=['All', 'Active', 'Completed', 'Cancelled'],
            help='Filter orders by status (default: All)'
        )
        
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Username to associate with the sync (default: None)'
        )
    
    def handle(self, *args, **options):
        """Execute the command"""
        
        # Check if eBay is configured
        if not EbayConfig.is_configured():
            raise CommandError(
                'eBay API is not properly configured. '
                'Please check your .env file and ensure all eBay credentials are set.'
            )
        
        self.stdout.write(self.style.NOTICE('Starting eBay order sync...'))
        
        # Get options
        days = options['days']
        status = options['status']
        username = options['user']
        
        # Get user if specified
        user = None
        if username:
            try:
                user = User.objects.get(username=username)
                self.stdout.write(f'Orders will be associated with user: {username}')
            except User.DoesNotExist:
                raise CommandError(f'User "{username}" does not exist')
        
        # Display sync parameters
        days_text = days if days else EbayConfig.DAYS_TO_FETCH
        self.stdout.write(f'Fetching orders from last {days_text} days')
        self.stdout.write(f'Order status filter: {status}')
        
        try:
            # Initialize eBay service
            ebay_service = EbayService()
            
            # Fetch orders from eBay
            self.stdout.write(self.style.NOTICE('Fetching orders from eBay...'))
            ebay_orders = ebay_service.fetch_orders(days_back=days, order_status=status)
            
            if not ebay_orders:
                self.stdout.write(self.style.WARNING('No orders found in the specified date range'))
                return
            
            self.stdout.write(f'Found {len(ebay_orders)} orders from eBay')
            
            # Sync each order to database
            created_count = 0
            skipped_count = 0
            error_count = 0
            
            for ebay_order in ebay_orders:
                order_id = ebay_order.get('OrderID', 'Unknown')
                
                try:
                    order, created = ebay_service.sync_order_to_db(ebay_order, user=user)
                    
                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Created order {order.order_number} (eBay: {order_id})'
                            )
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'⊘ Skipped order {order_id} (already exists as {order.order_number})'
                            )
                        )
                
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Error processing order {order_id}: {str(e)}'
                        )
                    )
                    logger.exception(f'Error syncing eBay order {order_id}')
            
            # Summary
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=== Sync Summary ==='))
            self.stdout.write(f'Total orders found: {len(ebay_orders)}')
            self.stdout.write(self.style.SUCCESS(f'Created: {created_count}'))
            self.stdout.write(self.style.WARNING(f'Skipped: {skipped_count}'))
            
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'Errors: {error_count}'))
            else:
                self.stdout.write(f'Errors: {error_count}')
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('eBay order sync completed!'))
        
        except Exception as e:
            raise CommandError(f'Error during eBay sync: {str(e)}')
