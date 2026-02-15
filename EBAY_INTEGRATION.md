# eBay Integration Documentation

## Overview

This integration allows you to automatically fetch orders from eBay and save them to your database with the source set to 'EBAY'.

## Setup Instructions

### 1. Get eBay API Credentials

1. Go to [eBay Developer Portal](https://developer.ebay.com/signin)
2. Login with your credentials:
   - Username: `ab_279606`
   - Password: `Wims@2026`

3. Navigate to **My Account** → **Keys**
4. Get the following credentials:
   - **App ID (Client ID)**: Your application identifier
   - **Dev ID**: Your developer identifier
   - **Cert ID (Client Secret)**: Your application secret

5. Generate **User Token**:
   - Go to: https://developer.ebay.com/my/auth/?env=production&index=0
   - Select the appropriate scopes (at minimum: `https://api.ebay.com/oauth/api_scope/sell.fulfillment`)
   - Click "Get a Token from eBay via User Consent"
   - Complete the OAuth flow
   - Copy the generated token

### 2. Configure Environment Variables

Edit the `.env` file in your project root and add your eBay credentials:

```env
# eBay API Credentials
EBAY_APP_ID=your-app-id-here
EBAY_DEV_ID=your-dev-id-here
EBAY_CERT_ID=your-cert-id-here
EBAY_USER_TOKEN=your-user-token-here

# eBay Settings
EBAY_ENVIRONMENT=production  # or 'sandbox' for testing
EBAY_SITE_ID=0              # 0=US, 3=UK, 77=Germany
EBAY_DAYS_TO_FETCH=30       # How many days back to fetch
```

### 3. Install Dependencies

```bash
# Using virtual environment
venv/bin/pip install -r requirements.txt

# Or system-wide
pip3 install -r requirements.txt
```

The integration requires:
- `ebaysdk==2.2.0` - eBay SDK for Python
- `requests==2.31.0` - HTTP library
- `lxml` - XML processing (auto-installed with ebaysdk)

### 4. Run Migrations

```bash
venv/bin/python manage.py migrate orders
```

This adds the following fields:
- `OrderItem.ebay_item_id` - eBay Item ID reference
- `OrderItem.quantity_ordered` - Original quantity from eBay

## Usage

### Sync eBay Orders

Use the management command to fetch and sync orders:

```bash
# Fetch all orders from the last 30 days (default)
venv/bin/python manage.py sync_ebay_orders

# Fetch orders from the last 7 days
venv/bin/python manage.py sync_ebay_orders --days=7

# Fetch only active orders
venv/bin/python manage.py sync_ebay_orders --status=Active

# Fetch completed orders from last 14 days
venv/bin/python manage.py sync_ebay_orders --days=14 --status=Completed

# Associate orders with a specific user
venv/bin/python manage.py sync_ebay_orders --user=admin
```

### Command Options

- `--days` - Number of days to look back (default: from .env config)
- `--status` - Filter by status: `All`, `Active`, `Completed`, `Cancelled` (default: All)
- `--user` - Username to associate with synced orders

### Example Output

```
Starting eBay order sync...
Fetching orders from last 30 days
Order status filter: All
Found 15 orders from eBay

✓ Created order ORD-20260209-0001 (eBay: 123456789)
✓ Created order ORD-20260209-0002 (eBay: 987654321)
⊘ Skipped order 111222333 (already exists as ORD-20260208-0045)
✗ Error processing order 444555666: Product not found

=== Sync Summary ===
Total orders found: 15
Created: 12
Skipped: 2
Errors: 1

eBay order sync completed!
```

## Data Mapping

### Order Fields

eBay Field → Database Field:
- `OrderID` → `external_order_id`
- `BuyerUserID` → `customer_name` (if shipping name not available)
- `ShippingAddress.Name` → `customer_name`
- `ShippingAddress.*` → `shipping_address_*`
- `Total` → `total_amount`
- `Subtotal` → `subtotal`
- `ShippingServiceCost` → `shipping_cost`
- `CreatedTime` → `order_date`
- `PaidTime` → `confirmed_date`
- `ShippedTime` → `shipped_date`
- `ShipmentTrackingNumber` → `tracking_number`
- Source is automatically set to `EBAY`

### Order Status Mapping

- eBay `Active` → `PROCESSING`
- eBay `Completed` → `DELIVERED`
- eBay `Cancelled` → `CANCELLED`
- eBay `Inactive` → `CANCELLED`
- Default → `PENDING`

### Payment Status Mapping

- eBay `Complete` → `PAID`
- eBay `Pending` → `UNPAID`
- eBay `Failed` → `FAILED`
- Default → `UNPAID`

### Order Items

Each transaction in the eBay order creates an OrderItem:
- If a product with matching SKU exists, it's linked
- Otherwise, SKU and product name are stored as text
- eBay Item ID is stored for reference
- Quantity and pricing are preserved from eBay

## Programmatic Usage

You can also use the eBay service directly in your code:

```python
from orders.services.ebay_service import EbayService

# Initialize service
ebay_service = EbayService()

# Fetch orders
orders = ebay_service.fetch_orders(days_back=7, order_status='Active')

# Sync individual order
for ebay_order in orders:
    order, created = ebay_service.sync_order_to_db(ebay_order, user=request.user)
    if created:
        print(f"Created order: {order.order_number}")
```

## Automation

### Set up Cron Job

To automatically sync orders daily:

```bash
# Edit crontab
crontab -e

# Add this line to sync every day at 2 AM
0 2 * * * cd /path/to/Inventory && venv/bin/python manage.py sync_ebay_orders --days=2
```

### Django Background Task

Or use Django Q, Celery, or similar:

```python
# In your tasks.py
from django.core.management import call_command

def sync_ebay_orders_task():
    call_command('sync_ebay_orders', days=2)
```

## Troubleshooting

### "eBay API credentials not properly configured"

Make sure all required variables are set in `.env`:
- EBAY_APP_ID
- EBAY_DEV_ID
- EBAY_CERT_ID
- EBAY_USER_TOKEN

### "No module named 'ebaysdk'"

Install dependencies:
```bash
venv/bin/pip install -r requirements.txt
```

### "ConnectionError" or API timeouts

1. Check your internet connection
2. Verify credentials are correct
3. Check if eBay API is accessible
4. Verify the EBAY_ENVIRONMENT setting matches your credentials

### Token Expired

User tokens expire. Generate a new one:
1. Go to: https://developer.ebay.com/my/auth/?env=production&index=0
2. Generate new token
3. Update EBAY_USER_TOKEN in `.env`

### Orders Not Syncing

1. Check date range - ensure orders exist in the specified period
2. Verify order status filter matches your orders
3. Check if orders were already imported (they won't be duplicated)
4. Review error messages for specific issues

## API Limits

eBay API has rate limits:
- **Trading API**: 5,000 calls per day (production)
- **GetOrders**: Returns up to 100 orders per page

The sync command handles pagination automatically.

## Security Notes

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Protect User Token** - It provides access to your eBay account
3. **Use Sandbox for testing** - Set `EBAY_ENVIRONMENT=sandbox`
4. **Rotate tokens periodically** - Generate new tokens regularly

## Support

For eBay API documentation:
- https://developer.ebay.com/docs
- https://developer.ebay.com/devzone/xml/docs/reference/ebay/

For technical issues:
- Check Django logs
- Review eBay Developer forums
- Contact eBay Developer Support

## Files Created

- `orders/ebay_config.py` - Configuration management
- `orders/services/ebay_service.py` - eBay API integration
- `orders/management/commands/sync_ebay_orders.py` - Management command
- `.env` - Environment variables (not in git)
- `requirements.txt` - Updated with ebaysdk

## Database Changes

Migration: `orders/migrations/0003_orderitem_ebay_item_id_orderitem_quantity_ordered.py`
- Added `ebay_item_id` field to OrderItem
- Added `quantity_ordered` field to OrderItem
