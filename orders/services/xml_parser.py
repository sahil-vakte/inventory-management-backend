import xml.etree.ElementTree as ET
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ..models import Order, OrderItem
from stock.models import StockItem
from products.models import Product


class XMLOrderParser:
    """Parser for WIMS Order XML format"""
    
    def __init__(self):
        self.errors = []
        self.orders = []
    
    def parse_and_create_orders(self, xml_file, user=None):
        """
        Parse XML file and create orders
        
        Args:
            xml_file: File object containing XML data
            user: User creating the orders
        
        Returns:
            dict with created orders count, failed count, and error messages
        """
        try:
            # Parse XML
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            created_count = 0
            failed_count = 0
            created_orders = []
            errors = []
            
            # Flexible root element detection
            # Accept various root element names (case-insensitive)
            root_tag_lower = root.tag.lower()
            
            # Multiple orders container (Orders, web_orders, OrdersList, etc.)
            if root_tag_lower in ['orders', 'web_orders', 'orderslist', 'orderlist']:
                # Try to find Order elements (case-insensitive)
                order_elements = root.findall('Order')
                if not order_elements:
                    order_elements = root.findall('order')
                if not order_elements:
                    # Try to find all direct children that might be orders
                    order_elements = list(root)
            # Single order
            elif root_tag_lower in ['order', 'web_order']:
                order_elements = [root]
            else:
                # Try to treat it as a container with order children
                order_elements = root.findall('Order')
                if not order_elements:
                    order_elements = root.findall('order')
                if not order_elements:
                    # Last resort: treat all children as potential orders
                    order_elements = list(root)
                
                if not order_elements:
                    raise ValueError(
                        f"Invalid XML structure. Root element '{root.tag}' found, but no order elements detected. "
                        f"Expected root elements: 'Orders', 'Order', 'web_orders', or similar."
                    )
            
            # Process each order
            for order_elem in order_elements:
                try:
                    with transaction.atomic():
                        order = self._parse_order_element(order_elem, user)
                        created_orders.append({
                            'order_number': order.order_number,
                            'customer_name': order.customer_name,
                            'total_amount': str(order.total_amount)
                        })
                        created_count += 1
                except Exception as e:
                    failed_count += 1
                    order_ref = self._get_text(order_elem, 'OrderNumber', 'Unknown')
                    errors.append({
                        'order_reference': order_ref,
                        'error': str(e)
                    })
            
            return {
                'created_count': created_count,
                'failed_count': failed_count,
                'orders': created_orders,
                'errors': errors
            }
        
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML format: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error processing XML: {str(e)}")
    
    def _parse_order_element(self, order_elem, user=None):
        """Parse a single Order XML element and create Order object - supports WIMS format"""
        
        # WIMS XML has nested structure: <web_order><order>, <customer>, <payment>, <products>
        order_node = order_elem.find('order')
        customer_node = order_elem.find('customer')
        payment_node = order_elem.find('payment')
        
        # If no nested structure, treat order_elem as the order node (fallback)
        if order_node is None:
            order_node = order_elem
        
        # Extract order data
        order_data = {
            'external_order_id': self._get_text(order_node, 'order_reference') or self._get_text(order_node, 'order_id') or self._get_text(order_elem, 'OrderNumber'),
            'order_source': 'XML',
            'created_by': user,
        }
        
        # Parse customer info from WIMS <customer> node
        if customer_node is not None:
            billing_firstname = self._get_text(customer_node, 'billing_firstname', '')
            billing_lastname = self._get_text(customer_node, 'billing_lastname', '')
            order_data['customer_name'] = f"{billing_firstname} {billing_lastname}".strip() or self._get_text(customer_node, 'billing_fullname', required=True)
            order_data['customer_email'] = self._get_text(customer_node, 'billing_email') or self._get_text(customer_node, 'email_address')
            order_data['customer_phone'] = self._get_text(customer_node, 'billing_telephone') or self._get_text(customer_node, 'billing_mobile')
            order_data['customer_company'] = self._get_text(customer_node, 'billing_company_name')
            
            # Billing address from WIMS
            order_data['billing_address_line1'] = self._get_text(customer_node, 'billing_address1')
            order_data['billing_address_line2'] = self._get_text(customer_node, 'billing_address2')
            order_data['billing_city'] = self._get_text(customer_node, 'billing_town') or self._get_text(customer_node, 'billing_city')
            order_data['billing_state'] = self._get_text(customer_node, 'billing_county')
            order_data['billing_postal_code'] = self._get_text(customer_node, 'billing_postcode')
            order_data['billing_country'] = self._get_text(customer_node, 'billing_country_name', 'UK')
            
            # Shipping address from WIMS
            order_data['shipping_address_line1'] = self._get_text(customer_node, 'delivery_address1')
            order_data['shipping_address_line2'] = self._get_text(customer_node, 'delivery_address2')
            order_data['shipping_city'] = self._get_text(customer_node, 'delivery_town') or self._get_text(customer_node, 'delivery_city')
            order_data['shipping_state'] = self._get_text(customer_node, 'delivery_county')
            order_data['shipping_postal_code'] = self._get_text(customer_node, 'delivery_postcode')
            order_data['shipping_country'] = self._get_text(customer_node, 'delivery_country_name', 'UK')
        else:
            # Fallback to simple structure
            order_data['customer_name'] = self._get_text(order_elem, 'CustomerName', required=True)
            order_data['customer_email'] = self._get_text(order_elem, 'CustomerEmail')
            order_data['customer_phone'] = self._get_text(order_elem, 'CustomerPhone')
            order_data['customer_company'] = self._get_text(order_elem, 'CustomerCompany')
            
            # Parse customer info (alternative structure)
            customer_info = order_elem.find('CustomerInfo')
            if customer_info is not None:
                order_data['customer_name'] = self._get_text(customer_info, 'Name', order_data.get('customer_name'))
                order_data['customer_email'] = self._get_text(customer_info, 'Email', order_data.get('customer_email'))
                order_data['customer_phone'] = self._get_text(customer_info, 'Phone', order_data.get('customer_phone'))
                order_data['customer_company'] = self._get_text(customer_info, 'Company', order_data.get('customer_company'))
            
            # Parse shipping address
            shipping_address = order_elem.find('ShippingAddress')
            if shipping_address is not None:
                order_data['shipping_address_line1'] = self._get_text(shipping_address, 'AddressLine1')
                order_data['shipping_address_line2'] = self._get_text(shipping_address, 'AddressLine2')
                order_data['shipping_city'] = self._get_text(shipping_address, 'City')
                order_data['shipping_state'] = self._get_text(shipping_address, 'State')
                order_data['shipping_postal_code'] = self._get_text(shipping_address, 'PostalCode')
                order_data['shipping_country'] = self._get_text(shipping_address, 'Country', 'UK')
            
            # Parse billing address
            billing_address = order_elem.find('BillingAddress')
            if billing_address is not None:
                order_data['billing_address_line1'] = self._get_text(billing_address, 'AddressLine1')
                order_data['billing_address_line2'] = self._get_text(billing_address, 'AddressLine2')
                order_data['billing_city'] = self._get_text(billing_address, 'City')
                order_data['billing_state'] = self._get_text(billing_address, 'State')
                order_data['billing_postal_code'] = self._get_text(billing_address, 'PostalCode')
                order_data['billing_country'] = self._get_text(billing_address, 'Country', 'UK')
        
        # Ensure billing = shipping if billing is empty
        if not order_data.get('billing_address_line1') and order_data.get('shipping_address_line1'):
            order_data['billing_address_line1'] = order_data['shipping_address_line1']
            order_data['billing_address_line2'] = order_data['shipping_address_line2']
            order_data['billing_city'] = order_data['shipping_city']
            order_data['billing_state'] = order_data['shipping_state']
            order_data['billing_postal_code'] = order_data['shipping_postal_code']
            order_data['billing_country'] = order_data['shipping_country']
        
        
        # Parse dates from WIMS format
        order_date_str = self._get_text(order_node, 'order_date') or self._get_text(order_elem, 'OrderDate')
        if order_date_str and order_date_str != '0000-00-00 00:00:00':
            order_data['order_date'] = self._parse_datetime(order_date_str)
        
        delivery_date_str = self._get_text(order_node, 'dispatch_date') or self._get_text(order_elem, 'ExpectedDeliveryDate')
        if delivery_date_str and delivery_date_str != '0000-00-00 00:00:00':
            order_data['expected_delivery_date'] = self._parse_datetime(delivery_date_str)
        
        # Parse financial data from WIMS format
        order_data['subtotal'] = self._get_decimal(order_node, 'product_total_ex') or self._get_decimal(order_elem, 'Subtotal', Decimal('0.00'))
        order_data['tax_amount'] = self._get_decimal(order_node, 'grand_total_vat') or self._get_decimal(order_elem, 'TaxAmount', Decimal('0.00'))
        order_data['tax_rate'] = Decimal('20.00')  # WIMS uses 20% VAT
        order_data['shipping_cost'] = self._get_decimal(order_node, 'shipping_total_ex') or self._get_decimal(order_elem, 'ShippingCost', Decimal('0.00'))
        order_data['discount_amount'] = self._get_decimal(order_node, 'discount_ex') or self._get_decimal(order_elem, 'DiscountAmount', Decimal('0.00'))
        order_data['total_amount'] = self._get_decimal(order_node, 'grand_total_inc') or self._get_decimal(order_elem, 'TotalAmount', Decimal('0.00'))
        
        # Parse payment info from WIMS <payment> node
        if payment_node is not None:
            order_data['payment_method'] = self._get_text(payment_node, 'payment_type')
            order_data['payment_reference'] = self._get_text(payment_node, 'transaction_reference')
            order_data['payment_status'] = 'PAID'  # WIMS exports are typically paid
        else:
            order_data['payment_method'] = self._get_text(order_elem, 'PaymentMethod')
            order_data['payment_reference'] = self._get_text(order_elem, 'PaymentReference')
            payment_status = self._get_text(order_elem, 'PaymentStatus', 'UNPAID').upper()
            if payment_status in dict(Order.PAYMENT_STATUS_CHOICES).keys():
                order_data['payment_status'] = payment_status
        
        # Parse shipping info from WIMS
        order_data['shipping_method'] = self._get_text(order_node, 'courier_name') or self._get_text(order_elem, 'ShippingMethod')
        order_data['tracking_number'] = self._get_text(order_elem, 'TrackingNumber')
        order_data['carrier'] = self._get_text(order_node, 'courier_name') or self._get_text(order_elem, 'Carrier')
        
        # Parse status - WIMS uses order_state
        order_state = self._get_text(order_node, 'order_state', '')
        if 'payment received' in order_state.lower() or 'paid' in order_state.lower():
            order_data['order_status'] = 'CONFIRMED'
            order_data['payment_status'] = 'PAID'
        elif 'dispatch' in order_state.lower() or 'ship' in order_state.lower():
            order_data['order_status'] = 'SHIPPED'
        else:
            order_status = self._get_text(order_elem, 'OrderStatus', 'PENDING').upper()
            if order_status in dict(Order.STATUS_CHOICES).keys():
                order_data['order_status'] = order_status
        
        
        # Parse notes from WIMS
        order_data['customer_notes'] = self._get_text(order_node, 'order_customer_comments') or self._get_text(order_elem, 'CustomerNotes')
        order_data['internal_notes'] = self._get_text(order_node, 'order_notes') or self._get_text(order_elem, 'InternalNotes')
        
        # Create order
        order = Order.objects.create(**order_data)
        
        # Parse and create order items from WIMS <products> node
        products_elem = order_elem.find('products')
        if products_elem is not None:
            for item_elem in products_elem.findall('product'):
                self._parse_order_item(item_elem, order, is_wims_format=True)
        else:
            # Fallback to standard <Items> structure
            items_elem = order_elem.find('Items')
            if items_elem is not None:
                for item_elem in items_elem.findall('Item'):
                    self._parse_order_item(item_elem, order, is_wims_format=False)
        
        # Recalculate totals if not provided
        if order_data['total_amount'] == Decimal('0.00'):
            order.calculate_totals()
            order.save()
        
        return order
    
    def _parse_order_item(self, item_elem, order, is_wims_format=False):
        """Parse a single Item XML element and create OrderItem, assigning location from related product if available"""

        if is_wims_format:
            sku = self._get_text(item_elem, 'reference', required=True)
            quantity = int(self._get_text(item_elem, 'quantity', '1'))
            unit_price = self._get_decimal(item_elem, 'price_inc', Decimal('0.00'))
            product_name = self._get_text(item_elem, 'title', sku)
            tax_rate = self._get_decimal(item_elem, 'tax_rate', Decimal('20.00'))
        else:
            sku = self._get_text(item_elem, 'SKU', required=True)
            quantity = int(self._get_text(item_elem, 'Quantity', '1'))
            unit_price = self._get_decimal(item_elem, 'UnitPrice', Decimal('0.00'))
            product_name = self._get_text(item_elem, 'ProductName', sku)
            tax_rate = self._get_decimal(item_elem, 'TaxRate', Decimal('20.00'))

        item_data = {
            'order': order,
            'sku': sku,
            'quantity': quantity,
            'unit_price': unit_price,
            'product_name': product_name,
            'product_type': self._get_text(item_elem, 'ProductType'),
            'color_code': self._get_text(item_elem, 'ColorCode'),
            'tax_rate': tax_rate,
            'discount_amount': self._get_decimal(item_elem, 'DiscountAmount', Decimal('0.00')),
            'notes': self._get_text(item_elem, 'Notes'),
        }

        # Try to find product by SKU and assign location if available
        try:
            product = Product.objects.get(child_reference=sku)
            item_data['product'] = product
            # If you want to denormalize location, add here (e.g., item_data['location'] = product.location)
        except Product.DoesNotExist:
            pass

        # Try to find stock item by SKU
        try:
            stock_item = StockItem.objects.get(sku=sku)
            item_data['stock_item'] = stock_item
            if not item_data.get('product_type'):
                item_data['product_type'] = stock_item.product_type
            if not item_data.get('color_code'):
                item_data['color_code'] = stock_item.color.color_code
            if not item_data.get('product_name') or item_data['product_name'] == sku:
                item_data['product_name'] = f"{stock_item.product_type} - {stock_item.color.color_name}"
            if unit_price == Decimal('0.00'):
                item_data['unit_price'] = stock_item.unit_cost
        except StockItem.DoesNotExist:
            pass

        order_item = OrderItem.objects.create(**item_data)

        if order_item.stock_item:
            try:
                order_item.reserve_stock()
            except Exception as e:
                order.internal_notes = (order.internal_notes or '') + f"\nWarning: Could not reserve stock for {sku}: {str(e)}"
                order.save()

        return order_item
    
    def _get_text(self, element, tag, default=None, required=False):
        """Safely extract text from XML element"""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        
        if required:
            raise ValueError(f"Required field '{tag}' not found in XML")
        
        return default
    
    def _get_decimal(self, element, tag, default=Decimal('0.00')):
        """Safely extract decimal value from XML element"""
        text = self._get_text(element, tag)
        if text:
            try:
                return Decimal(text)
            except:
                return default
        return default
    
    def _parse_datetime(self, date_string):
        """Parse datetime string in various formats"""
        from dateutil import parser
        try:
            return parser.parse(date_string)
        except:
            # If parsing fails, return current time
            return timezone.now()


class OrderXMLExporter:
    """Export orders to XML format"""
    
    @staticmethod
    def export_orders_to_xml(orders):
        """
        Export orders to XML format
        
        Args:
            orders: QuerySet or list of Order objects
        
        Returns:
            XML string
        """
        root = ET.Element('Orders')
        
        for order in orders:
            order_elem = OrderXMLExporter._create_order_element(order)
            root.append(order_elem)
        
        # Pretty print
        OrderXMLExporter._indent(root)
        tree = ET.ElementTree(root)
        
        import io
        output = io.BytesIO()
        tree.write(output, encoding='utf-8', xml_declaration=True)
        return output.getvalue().decode('utf-8')
    
    @staticmethod
    def _create_order_element(order):
        """Create XML element for a single order"""
        order_elem = ET.Element('Order')
        
        # Basic info
        ET.SubElement(order_elem, 'OrderNumber').text = order.order_number
        if order.external_order_id:
            ET.SubElement(order_elem, 'ExternalOrderID').text = order.external_order_id
        
        # Customer info
        customer_info = ET.SubElement(order_elem, 'CustomerInfo')
        ET.SubElement(customer_info, 'Name').text = order.customer_name
        if order.customer_email:
            ET.SubElement(customer_info, 'Email').text = order.customer_email
        if order.customer_phone:
            ET.SubElement(customer_info, 'Phone').text = order.customer_phone
        if order.customer_company:
            ET.SubElement(customer_info, 'Company').text = order.customer_company
        
        # Shipping address
        if order.shipping_address_line1:
            shipping = ET.SubElement(order_elem, 'ShippingAddress')
            ET.SubElement(shipping, 'AddressLine1').text = order.shipping_address_line1
            if order.shipping_address_line2:
                ET.SubElement(shipping, 'AddressLine2').text = order.shipping_address_line2
            if order.shipping_city:
                ET.SubElement(shipping, 'City').text = order.shipping_city
            if order.shipping_state:
                ET.SubElement(shipping, 'State').text = order.shipping_state
            if order.shipping_postal_code:
                ET.SubElement(shipping, 'PostalCode').text = order.shipping_postal_code
            ET.SubElement(shipping, 'Country').text = order.shipping_country
        
        # Dates
        ET.SubElement(order_elem, 'OrderDate').text = order.order_date.isoformat()
        if order.expected_delivery_date:
            ET.SubElement(order_elem, 'ExpectedDeliveryDate').text = order.expected_delivery_date.isoformat()
        
        # Financial
        ET.SubElement(order_elem, 'Subtotal').text = str(order.subtotal)
        ET.SubElement(order_elem, 'TaxAmount').text = str(order.tax_amount)
        ET.SubElement(order_elem, 'TaxRate').text = str(order.tax_rate)
        ET.SubElement(order_elem, 'ShippingCost').text = str(order.shipping_cost)
        ET.SubElement(order_elem, 'DiscountAmount').text = str(order.discount_amount)
        ET.SubElement(order_elem, 'TotalAmount').text = str(order.total_amount)
        
        # Status
        ET.SubElement(order_elem, 'OrderStatus').text = order.order_status
        ET.SubElement(order_elem, 'PaymentStatus').text = order.payment_status
        
        # Items
        items_elem = ET.SubElement(order_elem, 'Items')
        for item in order.items.all():
            item_elem = ET.SubElement(items_elem, 'Item')
            ET.SubElement(item_elem, 'SKU').text = item.sku
            ET.SubElement(item_elem, 'ProductName').text = item.product_name
            if item.product_type:
                ET.SubElement(item_elem, 'ProductType').text = item.product_type
            if item.color_code:
                ET.SubElement(item_elem, 'ColorCode').text = item.color_code
            ET.SubElement(item_elem, 'Quantity').text = str(item.quantity)
            ET.SubElement(item_elem, 'UnitPrice').text = str(item.unit_price)
            ET.SubElement(item_elem, 'LineTotal').text = str(item.line_total)
        
        return order_elem
    
    @staticmethod
    def _indent(elem, level=0):
        """Add pretty-print indentation to XML"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                OrderXMLExporter._indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
