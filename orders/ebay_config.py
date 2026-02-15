"""
eBay API Configuration
This module handles eBay API credentials and settings.
"""
from decouple import config


class EbayConfig:
    """Configuration class for eBay API credentials and settings"""
    
    # eBay API Credentials
    # Get these from: https://developer.ebay.com/my/keys
    APP_ID = config('EBAY_APP_ID', default='')
    DEV_ID = config('EBAY_DEV_ID', default='')
    CERT_ID = config('EBAY_CERT_ID', default='')
    
    # OAuth Token (User Token)
    # Generate from: https://developer.ebay.com/my/auth/?env=production&index=0
    USER_TOKEN = config('EBAY_USER_TOKEN', default='')
    
    # eBay API Settings
    ENVIRONMENT = config('EBAY_ENVIRONMENT', default='production')  # 'sandbox' or 'production'
    SITE_ID = config('EBAY_SITE_ID', default='0')  # 0 = US, 3 = UK, etc.
    
    # API Endpoints
    API_DOMAIN = {
        'sandbox': 'api.sandbox.ebay.com',
        'production': 'api.ebay.com'
    }
    
    # Order sync settings
    DAYS_TO_FETCH = config('EBAY_DAYS_TO_FETCH', default=30, cast=int)  # How many days back to fetch orders
    
    @classmethod
    def get_api_domain(cls):
        """Get the appropriate API domain based on environment"""
        return cls.API_DOMAIN.get(cls.ENVIRONMENT, cls.API_DOMAIN['production'])
    
    @classmethod
    def is_configured(cls):
        """Check if eBay API is properly configured"""
        return bool(cls.APP_ID and cls.DEV_ID and cls.CERT_ID and cls.USER_TOKEN)
    
    @classmethod
    def get_trading_api_config(cls):
        """Get configuration dict for Trading API"""
        return {
            'appid': cls.APP_ID,
            'devid': cls.DEV_ID,
            'certid': cls.CERT_ID,
            'token': cls.USER_TOKEN,
            'domain': cls.get_api_domain(),
            'warnings': True,
            'timeout': 20,
            'siteid': str(cls.SITE_ID),
        }
