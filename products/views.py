from rest_framework import mixins
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
import pandas as pd
from django.db import transaction
from django.db import models
from django.db import close_old_connections
from django.db.utils import OperationalError
from django.core.management.base import CommandError
from decimal import Decimal
import logging
import os
import tempfile
import threading
from .models import Product, ProductExtendedData, Category, Brand, Location
from .serializers import (
    ProductListSerializer, ProductDetailSerializer, 
    ProductCreateUpdateSerializer, CategorySerializer, BrandSerializer, LocationSerializer
)
from .management.commands.import_product_backup_csv import Command as ProductBackupCSVImportCommand
from stock.sku_utils import normalize_sku_reference

logger = logging.getLogger(__name__)

# Location CRUD API
class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['id', 'name']
    ordering = ['id']
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

    # No need to override create/update unless custom logic is needed, as serializer handles location validation and assignment.
    
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
        """Import products from Excel or the full product backup CSV file"""
        try:
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'No file provided'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            file = request.FILES['file']

            if file.name.lower().endswith('.csv'):
                return self._import_backup_csv(file, request)
            
            if not file.name.endswith(('.xlsx', '.xls')):
                return Response(
                    {'error': 'File must be Excel (.xlsx/.xls) or CSV (.csv) format'},
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
                            'parent_reference': normalize_sku_reference(row.get('Parent Reference')) if not pd.isna(row.get('Parent Reference')) else '',
                            'child_reference': normalize_sku_reference(
                                row.get('Child Reference', row.get('Child'))
                            ) if not pd.isna(row.get('Child Reference', row.get('Child'))) else '',
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

    def _import_backup_csv(self, uploaded_file, request):
        """Persist full backup CSV rows and project finalized fields into Product."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                tmp_path = tmp_file.name
                for chunk in uploaded_file.chunks():
                    tmp_file.write(chunk)

            importer = ProductBackupCSVImportCommand()
            batch_id = request.data.get('batch_id') or self._default_csv_batch_id(uploaded_file.name)
            chunk_size = self._to_positive_int(request.data.get('chunk_size'), 500)
            limit = self._to_optional_positive_int(request.data.get('limit'))
            dry_run = self._to_bool(request.data.get('dry_run'))
            skip_products = self._to_bool(request.data.get('skip_products'))
            run_sync = dry_run or limit is not None or self._to_bool(request.data.get('sync'))

            if not run_sync:
                self._start_background_csv_import(
                    tmp_path=tmp_path,
                    source_file_name=uploaded_file.name,
                    batch_id=batch_id,
                    chunk_size=chunk_size,
                    skip_products=skip_products,
                )
                tmp_path = None
                return Response({
                    'message': 'CSV import started in background',
                    'file_name': uploaded_file.name,
                    'mode': 'background',
                    'batch_id': batch_id,
                    'status_url': request.build_absolute_uri(
                        f'/api/v1/products/import-status/?batch_id={batch_id}'
                    ),
                    'note': 'Large CSV imports run in background to avoid request timeout. Re-uploading the same file updates existing rows instead of creating duplicates.',
                }, status=status.HTTP_202_ACCEPTED)

            stats = importer.import_file(
                file_path=tmp_path,
                batch_id=batch_id,
                chunk_size=chunk_size,
                limit=limit,
                dry_run=dry_run,
                skip_products=skip_products,
                write_output=False,
                source_file_name=uploaded_file.name,
            )

            return Response({
                'message': 'CSV import completed successfully' if not dry_run else 'CSV dry-run completed successfully',
                'file_name': uploaded_file.name,
                'mode': 'dry_run' if dry_run else 'import',
                'stats': stats,
            }, status=status.HTTP_200_OK)
        except CommandError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'Error importing CSV file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _start_background_csv_import(
        self, tmp_path, source_file_name, batch_id, chunk_size, skip_products
    ):
        thread = threading.Thread(
            target=self._run_background_csv_import,
            kwargs={
                'tmp_path': tmp_path,
                'source_file_name': source_file_name,
                'batch_id': batch_id,
                'chunk_size': chunk_size,
                'skip_products': skip_products,
            },
            daemon=True,
        )
        thread.start()

    def _run_background_csv_import(
        self, tmp_path, source_file_name, batch_id, chunk_size, skip_products
    ):
        try:
            close_old_connections()
            importer = ProductBackupCSVImportCommand()
            stats = importer.import_file(
                file_path=tmp_path,
                batch_id=batch_id,
                chunk_size=chunk_size,
                dry_run=False,
                skip_products=skip_products,
                write_output=False,
                source_file_name=source_file_name,
            )
            logger.info('Background product CSV import completed: %s', stats)
        except Exception:
            logger.exception(
                'Background product CSV import failed for %s batch %s',
                source_file_name,
                batch_id,
            )
        finally:
            close_old_connections()
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    @action(detail=False, methods=['get'], url_path='import-status')
    def import_status(self, request):
        """Get progress summary for a backup CSV import batch."""
        batch_id = request.query_params.get('batch_id')
        if not batch_id:
            return Response(
                {'error': 'batch_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rows = ProductExtendedData.objects.filter(import_batch_id=batch_id)
            summary = rows.aggregate(
                total_rows=models.Count('id'),
                linked_products=models.Count('product', distinct=True),
                latest_row_number=models.Max('row_number'),
                latest_created_at=models.Max('created_at'),
                latest_updated_at=models.Max('updated_at'),
            )
            return Response({
                'batch_id': batch_id,
                **summary,
            })
        except OperationalError as exc:
            if 'database is locked' in str(exc).lower():
                return Response({
                    'batch_id': batch_id,
                    'status': 'database_busy',
                    'message': 'Import is still writing records. Please retry status check in a few seconds.',
                }, status=status.HTTP_202_ACCEPTED)
            raise

    def _to_bool(self, value):
        if value is None:
            return False
        return str(value).strip().lower() in {'1', 'true', 'yes', 'y'}

    def _default_csv_batch_id(self, file_name):
        safe_name = os.path.splitext(os.path.basename(file_name))[0]
        return safe_name[:100] or 'product-backup-import'

    def _to_positive_int(self, value, default):
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    def _to_optional_positive_int(self, value):
        try:
            parsed = int(value)
            return parsed if parsed > 0 else None
        except (TypeError, ValueError):
            return None
    
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
