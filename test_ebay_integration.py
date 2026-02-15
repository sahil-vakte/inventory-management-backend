#!/usr/bin/env python
"""
Test eBay Integration Setup
This script verifies that the eBay integration is properly configured.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_management.settings')
django.setup()

from orders.ebay_config import EbayConfig
from orders.services.ebay_service import EbayService

def test_configuration():
    """Test if eBay is properly configured"""
    print("=" * 60)
    print("eBay Integration Configuration Test")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. Checking environment variables...")
    print(f"   EBAY_APP_ID: {'✓ Set' if EbayConfig.APP_ID and EbayConfig.APP_ID != 'your-app-id-here' else '✗ Not set'}")
    print(f"   EBAY_DEV_ID: {'✓ Set' if EbayConfig.DEV_ID and EbayConfig.DEV_ID != 'your-dev-id-here' else '✗ Not set'}")
    print(f"   EBAY_CERT_ID: {'✓ Set' if EbayConfig.CERT_ID and EbayConfig.CERT_ID != 'your-cert-id-here' else '✗ Not set'}")
    print(f"   EBAY_USER_TOKEN: {'✓ Set' if EbayConfig.USER_TOKEN and EbayConfig.USER_TOKEN != 'your-user-token-here' else '✗ Not set'}")
    print(f"   EBAY_ENVIRONMENT: {EbayConfig.ENVIRONMENT}")
    print(f"   EBAY_SITE_ID: {EbayConfig.SITE_ID}")
    
    # Check if configured
    print("\n2. Checking overall configuration...")
    if EbayConfig.is_configured():
        print("   ✓ eBay API is properly configured")
    else:
        print("   ✗ eBay API is NOT properly configured")
        print("\n   Please update the following in your .env file:")
        if not EbayConfig.APP_ID or EbayConfig.APP_ID == 'your-app-id-here':
            print("   - EBAY_APP_ID")
        if not EbayConfig.DEV_ID or EbayConfig.DEV_ID == 'your-dev-id-here':
            print("   - EBAY_DEV_ID")
        if not EbayConfig.CERT_ID or EbayConfig.CERT_ID == 'your-cert-id-here':
            print("   - EBAY_CERT_ID")
        if not EbayConfig.USER_TOKEN or EbayConfig.USER_TOKEN == 'your-user-token-here':
            print("   - EBAY_USER_TOKEN")
        print("\n   Get credentials from: https://developer.ebay.com/my/keys")
        print("   Login: ab_279606 / Wims@2026")
        return False
    
    # Try to initialize service
    print("\n3. Testing eBay service initialization...")
    try:
        service = EbayService()
        print("   ✓ eBay service initialized successfully")
        
        # Test API connection
        print("\n4. Testing API connection...")
        print("   Attempting to fetch orders from last 1 day...")
        try:
            orders = service.fetch_orders(days_back=1)
            print(f"   ✓ API connection successful!")
            print(f"   Found {len(orders)} order(s) in the last day")
            
            if len(orders) > 0:
                print("\n   Sample order:")
                sample = orders[0]
                print(f"   - Order ID: {sample.get('OrderID', 'N/A')}")
                print(f"   - Status: {sample.get('OrderStatus', 'N/A')}")
                print(f"   - Buyer: {sample.get('BuyerUserID', 'N/A')}")
                
        except Exception as e:
            print(f"   ✗ API connection failed: {str(e)}")
            print("\n   This could mean:")
            print("   - Invalid credentials")
            print("   - Token expired (regenerate at https://developer.ebay.com/my/auth/)")
            print("   - No orders in the specified timeframe")
            return False
            
    except Exception as e:
        print(f"   ✗ Failed to initialize service: {str(e)}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! eBay integration is ready to use.")
    print("=" * 60)
    print("\nRun this command to sync orders:")
    print("venv/bin/python manage.py sync_ebay_orders")
    
    return True

if __name__ == '__main__':
    success = test_configuration()
    sys.exit(0 if success else 1)
