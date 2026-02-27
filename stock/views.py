from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
import pandas as pd
from django.db import transaction, models
from decimal import Decimal
from .models import StockItem, StockMovement
from .serializers import (
    StockItemListSerializer, StockItemDetailSerializer, 
    StockItemCreateUpdateSerializer, StockMovementSerializer,
    StockAdjustmentSerializer
)

class StockItemViewSet(viewsets.ModelViewSet):
    """ViewSet for Stock Item CRUD operations with soft delete support"""
    queryset = StockItem.objects.all()  # Default queryset for router registration
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'product_type', 'color__color_code', 'is_active', 
        'is_discontinued', 'warehouse_location', 'is_deleted'
    ]
    search_fields = ['sku', 'product_type', 'color__color_name', 'supplier']
    ordering_fields = [
        'sku', 'product_type', 'available_stock_rolls', 
        'unit_cost', 'created_at'
    ]
    ordering = ['sku']
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        
        if include_deleted == 'true':
            queryset = StockItem.all_objects.select_related('color', 'product').prefetch_related('movements')
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            queryset = StockItem.all_objects.filter(is_deleted=True).select_related('color', 'product').prefetch_related('movements')
        else:
            queryset = StockItem.objects.select_related('color', 'product').prefetch_related('movements')
        
        # Filter by stock status
        stock_status = self.request.query_params.get('stock_status', None)
        if stock_status:
            if stock_status == 'low_stock':
                queryset = queryset.filter(
                    available_stock_rolls__lte=models.F('minimum_stock_level')
                )
            elif stock_status == 'out_of_stock':
                queryset = queryset.filter(available_stock_rolls=0)
            elif stock_status == 'in_stock':
                queryset = queryset.filter(available_stock_rolls__gt=0)
        
        # Filter by stock level range
        min_stock = self.request.query_params.get('min_stock', None)
        max_stock = self.request.query_params.get('max_stock', None)
        
        if min_stock:
            queryset = queryset.filter(available_stock_rolls__gte=min_stock)
        if max_stock:
            queryset = queryset.filter(available_stock_rolls__lte=max_stock)
        
        return queryset
    def get_serializer_class(self):
        if self.action == 'list':
            return StockItemListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return StockItemCreateUpdateSerializer
        return StockItemDetailSerializer
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to perform soft delete by default"""
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        
        if force_delete:
            instance.hard_delete()
            return Response({'message': 'Stock item permanently deleted'}, status=status.HTTP_204_NO_CONTENT)
        else:
            instance.soft_delete()
            return Response({'message': 'Stock item soft deleted'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted stock item"""
        try:
            stock_item = StockItem.all_objects.get(sku=pk)
            if not stock_item.is_deleted:
                return Response({'error': 'Stock item is not deleted'}, status=status.HTTP_400_BAD_REQUEST)
            
            stock_item.restore()
            serializer = self.get_serializer(stock_item)
            return Response({'message': 'Stock item restored successfully', 'data': serializer.data})
        except StockItem.DoesNotExist:
            return Response({'error': 'Stock item not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'], url_path='adjust-stock')
    def adjust_stock(self, request, pk=None):
        """Adjust stock levels for a specific item"""
        stock_item = self.get_object()
        serializer = StockAdjustmentSerializer(data=request.data)
        
        if serializer.is_valid():
            quantity = serializer.validated_data['quantity']
            reason = serializer.validated_data['reason']
            
            # Perform stock adjustment
            stock_item.adjust_stock(quantity, reason)
            
            return Response({
                'message': f'Stock adjusted by {quantity}',
                'new_stock_level': stock_item.available_stock_rolls,
                'reason': reason
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='reserve-stock')
    def reserve_stock(self, request, pk=None):
        """Reserve stock for an order"""
        stock_item = self.get_object()
        quantity = request.data.get('quantity', 0)
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response(
                    {'error': 'Quantity must be positive'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if stock_item.reserve_stock(quantity):
                return Response({
                    'message': f'Reserved {quantity} units',
                    'reserved_stock': stock_item.reserved_stock,
                    'available_stock': stock_item.total_available_stock
                })
            else:
                return Response(
                    {'error': 'Insufficient stock available'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except ValueError:
            return Response(
                {'error': 'Invalid quantity'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='release-stock')
    def release_stock(self, request, pk=None):
        """Release reserved stock"""
        stock_item = self.get_object()
        quantity = request.data.get('quantity', 0)
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response(
                    {'error': 'Quantity must be positive'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if stock_item.release_stock(quantity):
                return Response({
                    'message': f'Released {quantity} units',
                    'reserved_stock': stock_item.reserved_stock,
                    'available_stock': stock_item.total_available_stock
                })
            else:
                return Response(
                    {'error': 'Cannot release more stock than reserved'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except ValueError:
            return Response(
                {'error': 'Invalid quantity'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'], url_path='import-excel')
    def import_excel(self, request):
        """Import stock data from Excel file"""
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
                df = pd.read_excel(file, sheet_name='Current Stock')
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
                        if pd.isna(row.get('SKU')):
                            continue
                        
                        sku = str(row['SKU']).strip()
                        product_type = str(row.get('ProdTpe', '')).strip()
                        color_code = str(row.get('Color Abrvs', '')).strip()
                        available_stock = int(row.get('Available Stock (Rolls)', 0)) if not pd.isna(row.get('Available Stock (Rolls)')) else 0
                        
                        # Validate color exists
                        from colors.models import Color
                        try:
                            color = Color.objects.get(color_code=color_code)
                        except Color.DoesNotExist:
                            errors.append(f"Row {index + 1}: Color '{color_code}' not found")
                            continue
                        
                        # Create or update stock item
                        stock_item, created = StockItem.objects.update_or_create(
                            sku=sku,
                            defaults={
                                'product_type': product_type,
                                'color': color,
                                'available_stock_rolls': available_stock,
                            }
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
        """Get stock statistics"""
        try:
            total_items = StockItem.objects.count()
            active_items = StockItem.objects.filter(is_active=True).count()
            low_stock_items = StockItem.objects.filter(
                available_stock_rolls__lte=models.F('minimum_stock_level'),
                is_active=True
            ).count()
            out_of_stock_items = StockItem.objects.filter(
                available_stock_rolls=0,
                is_active=True
            ).count()
            
            # Stock value calculation
            total_stock_value = StockItem.objects.filter(
                is_active=True
            ).aggregate(
                total_value=models.Sum(
                    models.F('available_stock_rolls') * models.F('unit_cost')
                )
            )['total_value'] or 0
            
            # Total stock quantity
            total_stock_quantity = StockItem.objects.filter(
                is_active=True
            ).aggregate(
                total_quantity=models.Sum('available_stock_rolls')
            )['total_quantity'] or 0
            
            return Response({
                'total_items': total_items,
                'active_items': active_items,
                'low_stock_items': low_stock_items,
                'out_of_stock_items': out_of_stock_items,
                'total_stock_value': round(float(total_stock_value), 2),
                'total_stock_quantity': total_stock_quantity
            })
            
        except Exception as e:
            return Response(
                {'error': f'Error getting stats: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock(self, request):
        """Get items with low stock"""
        try:
            low_stock_items = StockItem.objects.filter(
                available_stock_rolls__lte=models.F('minimum_stock_level'),
                is_active=True
            ).select_related('color')
            
            serializer = self.get_serializer(low_stock_items, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': f'Error getting low stock items: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing Stock Movement history with soft delete support"""
    queryset = StockMovement.objects.all()  # Default queryset for router registration
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['movement_type', 'stock_item__sku', 'stock_item__product_type', 'is_deleted']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        
        if include_deleted == 'true':
            return StockMovement.all_objects.select_related('stock_item', 'stock_item__color')
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            return StockMovement.all_objects.filter(is_deleted=True).select_related('stock_item', 'stock_item__color')
        else:
            return StockMovement.objects.select_related('stock_item', 'stock_item__color')
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to perform soft delete by default"""
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        
        if force_delete:
            instance.hard_delete()
            return Response({'message': 'Stock movement permanently deleted'}, status=status.HTTP_204_NO_CONTENT)
        else:
            instance.soft_delete()
            return Response({'message': 'Stock movement soft deleted'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted stock movement"""
        try:
            movement = StockMovement.all_objects.get(id=pk)
            if not movement.is_deleted:
                return Response({'error': 'Stock movement is not deleted'}, status=status.HTTP_400_BAD_REQUEST)
            
            movement.restore()
            serializer = self.get_serializer(movement)
            return Response({'message': 'Stock movement restored successfully', 'data': serializer.data})
        except StockMovement.DoesNotExist:
            return Response({'error': 'Stock movement not found'}, status=status.HTTP_404_NOT_FOUND)
