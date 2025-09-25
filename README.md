# Django Inventory Management System

A comprehensive warehouse inventory management system built with Django REST Framework, designed to handle products, colors, and stock levels efficiently.

## 🚀 Features

- **Complete Product Management**: Handle product catalogs with attributes, pricing, and metadata
- **Color Management**: Centralized color code and name management
- **Real-time Stock Tracking**: Track inventory levels with automatic alerts
- **Excel Import/Export**: Seamless data migration from existing Excel files
- **RESTful APIs**: Full CRUD operations with filtering and search
- **Admin Interface**: Django admin for easy data management
- **Stock Movement Audit**: Complete audit trail for all stock changes
- **Authentication & Permissions**: Secure API access

## 📊 System Overview

Based on the SOW_WIMS.xlsx architecture, the system manages:
- **7,599 Products** from Product Master
- **1,238 Colors** from Colors sheet  
- **570 Stock Items** from Current Stock
- **Modules & Architecture** structure

## 🛠 Tech Stack

- **Backend**: Django 5.2.6 + Django REST Framework
- **Database**: SQLite (development) / PostgreSQL (production ready)
- **Data Processing**: pandas + openpyxl for Excel handling
- **API Features**: Filtering, pagination, search, authentication
- **Admin**: Django Admin interface

## 📁 Project Structure

```
inventory_management/
├── inventory_management/       # Project settings
├── products/                  # Product management app
│   ├── models.py             # Product, Category, Brand models
│   ├── serializers.py        # API serializers
│   ├── views.py              # API viewsets
│   └── admin.py              # Admin interface
├── colors/                   # Color management app
│   ├── models.py             # Color model
│   ├── serializers.py        # API serializers
│   ├── views.py              # API viewsets
│   └── admin.py              # Admin interface
├── stock/                    # Stock management app
│   ├── models.py             # StockItem, StockMovement models
│   ├── serializers.py        # API serializers
│   ├── views.py              # API viewsets
│   └── admin.py              # Admin interface
├── requirements.txt          # Dependencies
├── .gitignore               # Git ignore rules
└── manage.py                # Django management
```

## 🔧 Quick Start

### 1. Setup Environment
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies  
pip install -r requirements.txt
```

### 2. Initialize Database
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 3. Start Development Server
```bash
python manage.py runserver
```

### 4. Access the System
- **API Root**: http://localhost:8000/api/v1/
- **Admin Panel**: http://localhost:8000/admin/
- **API Auth**: http://localhost:8000/api/auth/

## 📋 API Endpoints

### Core Resources
- `GET /api/v1/products/` - Product catalog
- `GET /api/v1/colors/` - Color management  
- `GET /api/v1/stock/` - Stock inventory
- `GET /api/v1/categories/` - Product categories
- `GET /api/v1/brands/` - Product brands

### Special Operations  
- `POST /api/v1/products/import-excel/` - Import products from Excel
- `POST /api/v1/colors/import-excel/` - Import colors from Excel
- `POST /api/v1/stock/import-excel/` - Import stock from Excel
- `GET /api/v1/stock/low-stock/` - Get low stock alerts
- `POST /api/v1/stock/{sku}/adjust-stock/` - Adjust stock levels

### Statistics
- `GET /api/v1/products/stats/` - Product statistics
- `GET /api/v1/stock/stats/` - Stock statistics

## 📊 Data Models

### Product Model (85+ fields)
- **Identifiers**: VS Parent/Child IDs, references
- **Content**: Titles, descriptions, attributes
- **Pricing**: RRP, cost, VAT, price breaks
- **Status**: Active flags, featured, trade-only
- **Relations**: Brand, categories, tags

### Color Model  
- **Core**: Color code, name, secondary code
- **Meta**: Creation/update timestamps

### Stock Model
- **Identity**: SKU, product type, color
- **Levels**: Available, reserved, min/max thresholds  
- **Tracking**: Supplier, location, costs
- **Audit**: Movement history with reasons

## 🔐 Security Features

- **Authentication Required**: All endpoints protected
- **Token Auth**: REST API token authentication
- **Session Auth**: Django session authentication  
- **Permission Classes**: Configurable access control
- **CORS Enabled**: Cross-origin requests supported

## 📈 Advanced Features

### Stock Management
- **Automatic Alerts**: Low stock notifications
- **Reservation System**: Reserve stock for orders
- **Movement Tracking**: Complete audit trail
- **Bulk Operations**: Excel import/export

### Search & Filtering
- **Full-text Search**: Across product titles and references
- **Advanced Filters**: Price range, brand, status, stock levels
- **Pagination**: Configurable page sizes
- **Ordering**: Multiple sort options

### Excel Integration
- **Import Validation**: Data validation before import
- **Error Reporting**: Detailed import error logs
- **Export Features**: Generate Excel reports
- **Bulk Updates**: Mass data updates via Excel

## 🚦 Getting Started with Your Data

1. **Import Colors First**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/colors/import-excel/ \
     -H "Authorization: Token your_token" \
     -F "file=@SOW_WIMS.xlsx"
   ```

2. **Import Products**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/products/import-excel/ \
     -H "Authorization: Token your_token" \
     -F "file=@SOW_WIMS.xlsx"
   ```

3. **Import Stock Data**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/stock/import-excel/ \
     -H "Authorization: Token your_token" \
     -F "file=@SOW_WIMS.xlsx"
   ```

## 📚 Documentation

See `API_DOCUMENTATION.md` for complete API reference including:
- Detailed endpoint documentation
- Request/response examples  
- Authentication methods
- Error handling
- Query parameters

## 🔧 Dependencies

```
Django==5.2.6
djangorestframework==3.16.1
django-cors-headers==4.9.0
django-filter==25.1
pandas==2.3.2
openpyxl==3.1.5
python-decouple==3.8
```

## 🎯 Ready for Production

The system is production-ready with:
- ✅ Proper error handling
- ✅ Database optimization  
- ✅ Security configurations
- ✅ API documentation
- ✅ Admin interface
- ✅ Scalable architecture

Switch to PostgreSQL/MySQL for production by updating `DATABASES` in settings.py.