from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
import pandas as pd
from django.db import transaction
from django.db import models
from decimal import Decimal
from .models import Product, Category, Brand
from .serializers import (
    ProductListSerializer, ProductDetailSerializer, 
    ProductCreateUpdateSerializer, CategorySerializer, BrandSerializer
)

class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Category CRUD operations with soft delete support"""
    queryset = Category.objects.all()  # Default queryset for router registration
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['is_deleted', 'parent']
    search_fields = ['name']
    ordering = ['name']
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        if include_deleted == 'true':
            return Category.all_objects.all()
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            return Category.all_objects.filter(is_deleted=True)
        else:
            return Category.objects.all()
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to perform soft delete by default"""
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        
        if force_delete:
            instance.hard_delete()
            return Response({'message': 'Category permanently deleted'}, status=status.HTTP_204_NO_CONTENT)
        else:
            instance.soft_delete()
            return Response({'message': 'Category soft deleted'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted category"""
        try:
            category = Category.all_objects.get(id=pk)
            if not category.is_deleted:
                return Response({'error': 'Category is not deleted'}, status=status.HTTP_400_BAD_REQUEST)
            
            category.restore()
            serializer = self.get_serializer(category)
            return Response({'message': 'Category restored successfully', 'data': serializer.data})
        except Category.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

class BrandViewSet(viewsets.ModelViewSet):
    """ViewSet for Brand CRUD operations with soft delete support"""
    queryset = Brand.objects.all()  # Default queryset for router registration
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['is_deleted']
    search_fields = ['name']
    ordering = ['name']
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        if include_deleted == 'true':
            return Brand.all_objects.all()
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            return Brand.all_objects.filter(is_deleted=True)
        else:
            return Brand.objects.all()
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to perform soft delete by default"""
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        
        if force_delete:
            instance.hard_delete()
            return Response({'message': 'Brand permanently deleted'}, status=status.HTTP_204_NO_CONTENT)
        else:
            instance.soft_delete()
            return Response({'message': 'Brand soft deleted'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted brand"""
        try:
            brand = Brand.all_objects.get(id=pk)
            if not brand.is_deleted:
                return Response({'error': 'Brand is not deleted'}, status=status.HTTP_400_BAD_REQUEST)
            
            brand.restore()
            serializer = self.get_serializer(brand)
            return Response({'message': 'Brand restored successfully', 'data': serializer.data})
        except Brand.DoesNotExist:
            return Response({'error': 'Brand not found'}, status=status.HTTP_404_NOT_FOUND)

class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for Product CRUD operations with soft delete support"""
    queryset = Product.objects.all()  # Default queryset for router registration
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'brand', 'child_active', 'parent_active', 'featured', 
        'display_on_sale_page', 'trade_only_product', 'is_deleted'
    ]
    search_fields = [
        'child_reference', 'parent_reference', 'child_product_title', 
        'parent_product_title', 'product_subtitle'
    ]
    ordering_fields = [
        'vs_child_id', 'child_reference', 'child_product_title', 
        'rrp_price_inc_vat', 'created_at'
    ]
    ordering = ['vs_child_id']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        
        if include_deleted == 'true':
            queryset = Product.all_objects.select_related('brand').prefetch_related('categories')
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            queryset = Product.all_objects.filter(is_deleted=True).select_related('brand').prefetch_related('categories')
        else:
            queryset = Product.objects.select_related('brand').prefetch_related('categories')
        
        # Filter by active status
        active_only = self.request.query_params.get('active_only', None)
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(child_active=True, parent_active=True)
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price', None)
        max_price = self.request.query_params.get('max_price', None)
        
        if min_price:
            queryset = queryset.filter(rrp_price_inc_vat__gte=min_price)
        if max_price:
            queryset = queryset.filter(rrp_price_inc_vat__lte=max_price)
        
        return queryset
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to perform soft delete by default"""
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        
        if force_delete:
            instance.hard_delete()
            return Response({'message': 'Product permanently deleted'}, status=status.HTTP_204_NO_CONTENT)
        else:
            instance.soft_delete()
            return Response({'message': 'Product soft deleted'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted product"""
        try:
            product = Product.all_objects.get(vs_child_id=pk)
            if not product.is_deleted:
                return Response({'error': 'Product is not deleted'}, status=status.HTTP_400_BAD_REQUEST)
            
            product.restore()
            serializer = self.get_serializer(product)
            return Response({'message': 'Product restored successfully', 'data': serializer.data})
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'], url_path='import-excel')
    def import_excel(self, request):
        """Import products from Excel file"""
        try:
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'No file provided'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            file = request.FILES['file']
            
            if not file.name.endswith(('.xlsx', '.xls')):
                return Response(
                    {'error': 'File must be Excel format (.xlsx or .xls)'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Read Excel file
            try:
                df = pd.read_excel(file, sheet_name='Product Master')
            except Exception as e:
                return Response(
                    {'error': f'Error reading Excel file: {str(e)}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Import data
            created_count = 0
            updated_count = 0
            errors = []
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        if pd.isna(row.get('VS Child ID')):
                            continue
                        
                        vs_child_id = int(row['VS Child ID'])
                        
                        # Create or get brand
                        brand = None
                        if not pd.isna(row.get('Brand')):
                            brand_name = str(row['Brand']).strip()
                            brand, _ = Brand.objects.get_or_create(name=brand_name)
                        
                        # Prepare product data
                        product_data = {
                            'vs_parent_id': int(row.get('VS Parent ID', 0)) if not pd.isna(row.get('VS Parent ID')) else 0,
                            'parent_reference': str(row.get('Parent Reference', '')).strip() if not pd.isna(row.get('Parent Reference')) else '',
                            'child_reference': str(row.get('Child', '')).strip() if not pd.isna(row.get('Child')) else '',
                            'parent_product_title': str(row.get('Parent Product Title', '')).strip() if not pd.isna(row.get('Parent Product Title')) else '',
                            'child_product_title': str(row.get('Child Product Title', '')).strip() if not pd.isna(row.get('Child Product Title')) else '',
                            'product_subtitle': str(row.get('Product Subtitle', '')).strip() if not pd.isna(row.get('Product Subtitle')) else '',
                            'product_summary': str(row.get('Product Summary', '')).strip() if not pd.isna(row.get('Product Summary')) else '',
                            'product_description': str(row.get('Product Description', '')).strip() if not pd.isna(row.get('Product Description')) else '',
                            'brand': brand,
                            
                            # Attributes
                            'attribute_colour': str(row.get('Attribute 2 (Colour)', '')).strip() if not pd.isna(row.get('Attribute 2 (Colour)')) else '',
                            'attribute_length': str(row.get('Attribute 1 (Length)', '')).strip() if not pd.isna(row.get('Attribute 1 (Length)')) else '',
                            'attribute_size': str(row.get('Attribute 8 (Size)', '')).strip() if not pd.isna(row.get('Attribute 8 (Size)')) else '',
                            
                            # Pricing
                            'rrp_price_inc_vat': Decimal(str(row.get('RRP Price (Inc VAT)', 0))) if not pd.isna(row.get('RRP Price (Inc VAT)')) else Decimal('0.00'),
                            'cost_price_inc_vat': Decimal(str(row.get('Cost Price (Inc VAT)', 0))) if not pd.isna(row.get('Cost Price (Inc VAT)')) else Decimal('0.00'),
                            'deposit_price_inc_vat': Decimal(str(row.get('Deposit Price (Inc VAT)', 0))) if not pd.isna(row.get('Deposit Price (Inc VAT)')) else Decimal('0.00'),
                            'vat_rate': Decimal(str(row.get('VAT Rate', 20))) if not pd.isna(row.get('VAT Rate')) else Decimal('20.00'),
                            
                            # Status
                            'child_active': str(row.get('Child Active', 'N')).upper() == 'Y',
                            'parent_active': str(row.get('Parent Active', 'N')).upper() == 'Y',
                            'featured': str(row.get('Featured', 'N')).upper() == 'Y',
                            'display_on_sale_page': str(row.get('Display On Sale Page', 'Y')).upper() == 'Y',
                            'trade_only_product': str(row.get('Trade Only Product', 'N')).upper() == 'Y',
                            
                            # Weight and stock
                            'weight_kg': Decimal(str(row.get('Weight (in KGs)', 0))) if not pd.isna(row.get('Weight (in KGs)')) else Decimal('0.000'),
                            'stock_value': Decimal(str(row.get('Stock Value', 0))) if not pd.isna(row.get('Stock Value')) else Decimal('0.00'),
                            'min_purchase_quantity': int(row.get('Min Purchase Quantity', 1)) if not pd.isna(row.get('Min Purchase Quantity')) else 1,
                            'max_purchase_quantity': int(row.get('Max Purchase Quantity', 0)) if not pd.isna(row.get('Max Purchase Quantity')) else 0,
                        }
                        
                        # Get or create product
                        product, created = Product.objects.update_or_create(
                            vs_child_id=vs_child_id,
                            defaults=product_data
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                            
                    except Exception as e:
                        errors.append(f"Row {index + 1}: {str(e)}")
            
            return Response({
                'message': 'Import completed successfully',
                'created': created_count,
                'updated': updated_count,
                'errors': errors[:10]  # Limit errors to first 10
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Unexpected error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Get product statistics"""
        try:
            total_products = Product.objects.count()
            active_products = Product.objects.filter(child_active=True, parent_active=True).count()
            featured_products = Product.objects.filter(featured=True).count()
            brands_count = Brand.objects.count()
            categories_count = Category.objects.count()
            
            # Price statistics
            products_with_price = Product.objects.filter(rrp_price_inc_vat__gt=0)
            avg_price = products_with_price.aggregate(
                avg_price=models.Avg('rrp_price_inc_vat')
            )['avg_price'] or 0
            
            return Response({
                'total_products': total_products,
                'active_products': active_products,
                'featured_products': featured_products,
                'brands_count': brands_count,
                'categories_count': categories_count,
                'average_price': round(float(avg_price), 2)
            })
            
        except Exception as e:
            return Response(
                {'error': f'Error getting stats: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
