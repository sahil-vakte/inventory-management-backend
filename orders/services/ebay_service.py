"""
eBay Service Module
Handles interaction with eBay API to fetch and process orders.
"""
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal
import logging

from orders.ebay_config import EbayConfig
from orders.models import Order, OrderItem
from products.models import Product

logger = logging.getLogger(__name__)


class EbayService:
    """Service class to handle eBay API operations"""
    
    def __init__(self):
        """Initialize eBay Trading API connection"""
        if not EbayConfig.is_configured():
            raise ValueError("eBay API credentials not properly configured. Please check your .env file.")
        
        config = EbayConfig.get_trading_api_config()
        self.api = Trading(
            config_file=None,
            domain=config['domain'],
            appid=config['appid'],
            devid=config['devid'],
            certid=config['certid'],
            token=config['token'],
            siteid=config['siteid'],
            warnings=config['warnings'],
            timeout=config['timeout']
        )
    
    def fetch_orders(self, days_back=None, order_status=None):
        """
        Fetch orders from eBay
        
        Args:
            days_back (int): Number of days to look back for orders. Defaults to config setting.
            order_status (str): Filter by order status ('All', 'Active', 'Completed', etc.)
        
        Returns:
            list: List of order dictionaries from eBay
        """
        if days_back is None:
            days_back = EbayConfig.DAYS_TO_FETCH
        
        # Calculate date range
        end_time = timezone.now()
        start_time = end_time - timedelta(days=days_back)
        
        try:
            # Format dates for eBay API (ISO 8601 format)
            create_time_from = start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            create_time_to = end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            logger.info(f"Fetching eBay orders from {create_time_from} to {create_time_to}")
            
            # Call eBay GetOrders API
            response = self.api.execute('GetOrders', {
                'CreateTimeFrom': create_time_from,
                'CreateTimeTo': create_time_to,
                'OrderRole': 'Seller',
                'OrderStatus': order_status or 'All',
                'DetailLevel': 'ReturnAll',
                'Pagination': {
                    'EntriesPerPage': 100,
                    'PageNumber': 1
                }
            })
            
            # Parse response
            orders = []
            if response.reply.get('OrderArray'):
                order_array = response.reply.OrderArray.Order
                # Ensure it's always a list
                if not isinstance(order_array, list):
                    order_array = [order_array]
                orders = order_array
                logger.info(f"Successfully fetched {len(orders)} orders from eBay")
            else:
                logger.info("No orders found in the specified date range")
            
            return orders
            
        except ConnectionError as e:
            logger.error(f"eBay API connection error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error fetching eBay orders: {str(e)}")
            raise
    
    def parse_ebay_order(self, ebay_order):
        """
        Parse eBay order data into our Order model format
        
        Args:
            ebay_order (dict): Raw order data from eBay API
        
        Returns:
            dict: Parsed order data ready for Order model
        """
        try:
            # Extract order ID
            order_id = ebay_order.get('OrderID', '')
            
            # Extract buyer information
            buyer_user_id = ebay_order.get('BuyerUserID', '')
            shipping_address = ebay_order.get('ShippingAddress', {})
            
            # Extract financial information
            total_info = ebay_order.get('Total', {})
            subtotal_info = ebay_order.get('Subtotal', {})
            
            # Parse order status
            order_status = self._map_ebay_status(ebay_order.get('OrderStatus', ''))
            payment_status = self._map_payment_status(ebay_order.get('CheckoutStatus', {}).get('Status', ''))
            
            # Parse dates
            created_time = self._parse_ebay_date(ebay_order.get('CreatedTime'))
            paid_time = self._parse_ebay_date(ebay_order.get('PaidTime'))
            shipped_time = self._parse_ebay_date(ebay_order.get('ShippedTime'))
            
            # Extract shipping info
            shipping_service = ebay_order.get('ShippingServiceSelected', {})
            
            # Build order data
            order_data = {
                'external_order_id': order_id,
                'order_source': Order.SOURCE_EBAY,
                'customer_name': shipping_address.get('Name', buyer_user_id),
                'customer_email': ebay_order.get('TransactionArray', {}).get('Transaction', [{}])[0].get('Buyer', {}).get('Email', ''),
                'customer_phone': shipping_address.get('Phone', ''),
                
                # Shipping address
                'shipping_address_line1': shipping_address.get('Street1', ''),
                'shipping_address_line2': shipping_address.get('Street2', ''),
                'shipping_city': shipping_address.get('CityName', ''),
                'shipping_state': shipping_address.get('StateOrProvince', ''),
                'shipping_postal_code': shipping_address.get('PostalCode', ''),
                'shipping_country': shipping_address.get('CountryName', ''),
                
                # Order status
                'order_status': order_status,
                'payment_status': payment_status,
                
                # Dates
                'order_date': created_time,
                'confirmed_date': paid_time,
                'shipped_date': shipped_time,
                
                # Financial information
                'total_amount': Decimal(str(total_info.get('value', '0.00'))),
                'subtotal': Decimal(str(subtotal_info.get('value', '0.00'))),
                'shipping_cost': Decimal(str(ebay_order.get('ShippingServiceSelected', {}).get('ShippingServiceCost', {}).get('value', '0.00'))),
                'tax_amount': Decimal(str(ebay_order.get('Total', {}).get('value', '0.00'))) - Decimal(str(subtotal_info.get('value', '0.00'))),
                
                # Shipping info
                'shipping_method': shipping_service.get('ShippingService', ''),
                'tracking_number': ebay_order.get('ShippingDetails', {}).get('ShipmentTrackingDetails', [{}])[0].get('ShipmentTrackingNumber', ''),
                'carrier': ebay_order.get('ShippingDetails', {}).get('ShipmentTrackingDetails', [{}])[0].get('ShippingCarrierUsed', ''),
                
                # Payment info
                'payment_method': ebay_order.get('CheckoutStatus', {}).get('PaymentMethod', 'PayPal'),
                
                # Notes
                'customer_notes': ebay_order.get('BuyerCheckoutMessage', ''),
            }
            
            return order_data
            
        except Exception as e:
            logger.error(f"Error parsing eBay order {ebay_order.get('OrderID', 'Unknown')}: {str(e)}")
            raise
    
    def parse_order_items(self, ebay_order):
        """
        Parse eBay order items (line items)
        
        Args:
            ebay_order (dict): Raw order data from eBay API
        
        Returns:
            list: List of order item dictionaries
        """
        items = []
        transactions = ebay_order.get('TransactionArray', {}).get('Transaction', [])
        
        # Ensure transactions is always a list
        if not isinstance(transactions, list):
            transactions = [transactions]
        
        for transaction in transactions:
            item_data = transaction.get('Item', {})
            
            item = {
                'ebay_item_id': item_data.get('ItemID', ''),
                'sku': item_data.get('SKU', ''),
                'title': item_data.get('Title', ''),
                'quantity': int(transaction.get('QuantityPurchased', 1)),
                'unit_price': Decimal(str(transaction.get('TransactionPrice', {}).get('value', '0.00'))),
                'total_price': Decimal(str(transaction.get('TransactionPrice', {}).get('value', '0.00'))) * int(transaction.get('QuantityPurchased', 1)),
            }
            items.append(item)
        
        return items
    
    def sync_order_to_db(self, ebay_order, user=None):
        """
        Sync a single eBay order to the database
        
        Args:
            ebay_order (dict): Raw eBay order data
            user: Django User object (optional, for tracking who synced)
        
        Returns:
            tuple: (Order object, created boolean)
        """
        try:
            order_id = ebay_order.get('OrderID', '')
            
            # Check if order already exists
            existing_order = Order.objects.filter(external_order_id=order_id).first()
            
            if existing_order:
                logger.info(f"Order {order_id} already exists. Skipping.")
                return existing_order, False
            
            # Parse order data
            order_data = self.parse_ebay_order(ebay_order)
            
            # Set user if provided
            if user:
                order_data['created_by'] = user
            
            # Create order
            order = Order.objects.create(**order_data)
            
            # Parse and create order items
            items = self.parse_order_items(ebay_order)
            
            for item_data in items:
                # Try to find matching product by SKU
                product = None
                if item_data['sku']:
                    product = Product.objects.filter(sku=item_data['sku']).first()
                
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    sku=item_data['sku'] if not product else None,
                    product_name=item_data['title'],
                    quantity_ordered=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    line_total=item_data['total_price'],
                    ebay_item_id=item_data['ebay_item_id']
                )
            
            logger.info(f"Successfully synced eBay order {order_id} to database as {order.order_number}")
            return order, True
            
        except Exception as e:
            logger.error(f"Error syncing eBay order to database: {str(e)}")
            raise
    
    def _map_ebay_status(self, ebay_status):
        """Map eBay order status to our Order status"""
        status_map = {
            'Active': Order.STATUS_PROCESSING,
            'Completed': Order.STATUS_DELIVERED,
            'Cancelled': Order.STATUS_CANCELLED,
            'Inactive': Order.STATUS_CANCELLED,
        }
        return status_map.get(ebay_status, Order.STATUS_PENDING)
    
    def _map_payment_status(self, ebay_payment_status):
        """Map eBay payment status to our payment status"""
        payment_map = {
            'Complete': Order.PAYMENT_PAID,
            'Pending': Order.PAYMENT_UNPAID,
            'Failed': Order.PAYMENT_FAILED,
        }
        return payment_map.get(ebay_payment_status, Order.PAYMENT_UNPAID)
    
    def _parse_ebay_date(self, date_string):
        """Parse eBay date string to Django datetime"""
        if not date_string:
            return None
        
        try:
            # eBay uses ISO 8601 format
            dt = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S.%fZ')
            return timezone.make_aware(dt, timezone.utc)
        except (ValueError, TypeError):
            return None
