from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
import pandas as pd
from django.db import transaction, models
from django.utils import timezone
from decimal import Decimal
from .models import StockItem, StockMovement, StockBatch, StockBatchRoll
from .sku_utils import normalize_sku_reference
from .serializers import (
    StockItemListSerializer, StockItemDetailSerializer, 
    StockItemCreateUpdateSerializer, StockMovementSerializer,
    StockAdjustmentSerializer, StockBatchCreateSerializer,
    StockBatchListSerializer, StockBatchDetailSerializer,
    StockBatchLabelSerializer
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
        'sku', 'product_type', 'available_stock_in_mtr',
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
                    available_stock_in_mtr__lte=models.F('minimum_stock_level')
                )
            elif stock_status == 'out_of_stock':
                queryset = queryset.filter(available_stock_in_mtr=0)
            elif stock_status == 'in_stock':
                queryset = queryset.filter(available_stock_in_mtr__gt=0)
        
        # Filter by stock level range
        min_stock = self.request.query_params.get('min_stock', None)
        max_stock = self.request.query_params.get('max_stock', None)
        
        if min_stock:
            queryset = queryset.filter(available_stock_in_mtr__gte=min_stock)
        if max_stock:
            queryset = queryset.filter(available_stock_in_mtr__lte=max_stock)
        
        return queryset
    def get_serializer_class(self):
        if self.action == 'list':
            return StockItemListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return StockItemCreateUpdateSerializer
        return StockItemDetailSerializer

    def update(self, request, *args, **kwargs):
        """Use create/update serializer for validation but return detail serializer"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Return full detail serializer in response
        detail_serializer = StockItemDetailSerializer(instance)
        return Response(detail_serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
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
                'new_stock_level': stock_item.available_stock_in_mtr,
                'reason': reason
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='increment')
    def increment_stock(self, request, pk=None):
        """Increment stock by a positive quantity"""
        stock_item = self.get_object()
        qty = request.data.get('quantity', None)
        reason = request.data.get('reason', 'Increment via API')

        try:
            qty = int(qty)
        except (TypeError, ValueError):
            return Response({'error': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)

        if qty <= 0:
            return Response({'error': 'Quantity must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)

        stock_item.adjust_stock(qty, reason)
        return Response({
            'message': f'Stock increased by {qty}',
            'new_stock_level': stock_item.available_stock_in_mtr,
            'reason': reason
        })

    @action(detail=True, methods=['post'], url_path='decrement')
    def decrement_stock(self, request, pk=None):
        """Decrement stock by a positive quantity (will subtract from available stock)"""
        stock_item = self.get_object()
        qty = request.data.get('quantity', None)
        reason = request.data.get('reason', 'Decrement via API')

        try:
            qty = int(qty)
        except (TypeError, ValueError):
            return Response({'error': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)

        if qty <= 0:
            return Response({'error': 'Quantity must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)

        # Use negative quantity for adjustment
        stock_item.adjust_stock(-qty, reason)
        return Response({
            'message': f'Stock decreased by {qty}',
            'new_stock_level': stock_item.available_stock_in_mtr,
            'reason': reason
        })
    
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

    @action(detail=True, methods=['patch'], url_path='locations')
    def update_locations(self, request, pk=None):
        """Update primary and/or secondary location for a stock item.

        Accepts JSON body with optional keys `primary_location` and
        `secondary_location`. Use `null` to clear a location.
        """
        stock_item = self.get_object()
        data = request.data

        from products.models import Location

        errors = {}

        if 'primary_location' in data:
            val = data.get('primary_location')
            if val in [None, 'null', '']:
                stock_item.primary_location = None
            else:
                try:
                    loc = Location.objects.get(id=val)
                    stock_item.primary_location = loc
                except Location.DoesNotExist:
                    errors['primary_location'] = f"Location '{val}' not found"

        if 'secondary_location' in data:
            val = data.get('secondary_location')
            if val in [None, 'null', '']:
                stock_item.secondary_location = None
            else:
                try:
                    loc = Location.objects.get(id=val)
                    stock_item.secondary_location = loc
                except Location.DoesNotExist:
                    errors['secondary_location'] = f"Location '{val}' not found"

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        stock_item.save()
        serializer = StockItemDetailSerializer(stock_item)
        return Response(serializer.data)
    
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
                        
                        sku = normalize_sku_reference(row['SKU'])
                        product_type = normalize_sku_reference(row.get('ProdTpe', ''))[:20]
                        color_code = str(row.get('Color Abrvs', '')).strip()
                        raw_available_stock = row.get(
                            'Available Stock (Mtr)',
                            row.get('Available Stock (Rolls)', 0),
                        )
                        available_stock = int(raw_available_stock) if not pd.isna(raw_available_stock) else 0
                        
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
                                'available_stock_in_mtr': available_stock,
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
                available_stock_in_mtr__lte=models.F('minimum_stock_level'),
                is_active=True
            ).count()
            out_of_stock_items = StockItem.objects.filter(
                available_stock_in_mtr=0,
                is_active=True
            ).count()
            
            # Stock value calculation
            total_stock_value = StockItem.objects.filter(
                is_active=True
            ).aggregate(
                total_value=models.Sum(
                    models.F('available_stock_in_mtr') * models.F('unit_cost')
                )
            )['total_value'] or 0
            
            # Total stock quantity
            total_stock_quantity = StockItem.objects.filter(
                is_active=True
            ).aggregate(
                total_quantity=models.Sum('available_stock_in_mtr')
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
                available_stock_in_mtr__lte=models.F('minimum_stock_level'),
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


class StockBatchViewSet(viewsets.ModelViewSet):
    """Incoming stock batches with roll meterage and label data."""

    queryset = StockBatch.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'batch_id'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sku', 'supplier', 'created_by', 'batch_date', 'is_deleted']
    search_fields = ['batch_id', 'sku', 'product_name', 'supplier']
    ordering_fields = ['batch_id', 'sku', 'supplier', 'batch_date', 'total_meterage', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        if include_deleted == 'true':
            queryset = StockBatch.all_objects.all()
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            queryset = StockBatch.all_objects.filter(is_deleted=True)
        else:
            queryset = StockBatch.objects.all()

        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(batch_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(batch_date__lte=date_to)

        return queryset.select_related('stock_item', 'stock_item__product', 'created_by').prefetch_related('rolls')

    def get_serializer_class(self):
        if self.action == 'create':
            return StockBatchCreateSerializer
        if self.action == 'list':
            return StockBatchListSerializer
        return StockBatchDetailSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        if force_delete:
            instance.hard_delete()
            return Response({'message': 'Stock batch permanently deleted'}, status=status.HTTP_204_NO_CONTENT)

        instance.soft_delete()
        return Response({'message': 'Stock batch soft deleted'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, batch_id=None):
        try:
            stock_batch = StockBatch.all_objects.get(batch_id=batch_id)
        except StockBatch.DoesNotExist:
            return Response({'error': 'Stock batch not found'}, status=status.HTTP_404_NOT_FOUND)

        if not stock_batch.is_deleted:
            return Response({'error': 'Stock batch is not deleted'}, status=status.HTTP_400_BAD_REQUEST)

        stock_batch.restore()
        serializer = StockBatchDetailSerializer(stock_batch, context={'request': request})
        return Response({'message': 'Stock batch restored successfully', 'data': serializer.data})

    @action(detail=True, methods=['get'], url_path='labels')
    def labels(self, request, batch_id=None):
        stock_batch = self.get_object()
        labels = StockBatchLabelSerializer(stock_batch.rolls.all(), many=True).data
        return Response({
            'batch_id': stock_batch.batch_id,
            'labels': labels,
        })

    @action(detail=True, methods=['post'], url_path='mark-labels-generated')
    def mark_labels_generated(self, request, batch_id=None):
        stock_batch = self.get_object()
        return self._mark_batches_labels_generated([stock_batch], request.user)

    @action(detail=False, methods=['post'], url_path='mark-labels-generated')
    def bulk_mark_labels_generated(self, request):
        raw_ids = request.data.get('batch_ids') or request.data.get('batch_id')
        if isinstance(raw_ids, str):
            batch_ids = [part.strip() for part in raw_ids.split(',') if part.strip()]
        elif isinstance(raw_ids, (list, tuple)):
            batch_ids = [str(batch_id).strip() for batch_id in raw_ids if str(batch_id).strip()]
        else:
            batch_ids = [raw_ids] if raw_ids else []

        batch_ids = list(dict.fromkeys(batch_ids))
        if not batch_ids:
            return Response(
                {'error': 'At least one batch id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batches = list(
            StockBatch.objects.filter(batch_id__in=batch_ids)
            .select_related('stock_item', 'stock_item__product', 'created_by')
            .prefetch_related('rolls')
            .order_by('batch_id')
        )
        found_ids = {batch.batch_id for batch in batches}
        missing_ids = [batch_id for batch_id in batch_ids if batch_id not in found_ids]
        if missing_ids:
            return Response(
                {
                    'error': 'Some stock batches were not found',
                    'missing_batch_ids': missing_ids,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return self._mark_batches_labels_generated(batches, request.user)

    def _mark_batches_labels_generated(self, batches, user):
        now = timezone.now()
        batch_ids = [batch.batch_id for batch in batches]
        StockBatchRoll.objects.filter(batch__in=batches).update(
            label_generated=True,
            label_generated_at=now,
            label_generated_by_id=user.id if user and user.is_authenticated else None,
        )
        batch_payloads = []
        labels = []
        for batch in batches:
            batch_rolls = StockBatchRoll.objects.filter(batch=batch).order_by('roll_number')
            batch_labels = StockBatchLabelSerializer(batch_rolls, many=True).data
            labels.extend(batch_labels)
            batch_payloads.append({
                'batch_id': batch.batch_id,
                'labels': batch_labels,
            })

        return Response({
            'message': 'Labels marked as generated',
            'batch_id': batch_ids[0] if len(batch_ids) == 1 else None,
            'batch_ids': batch_ids,
            'updated_batch_count': len(batches),
            'updated_label_count': len(labels),
            'batches': batch_payloads,
            'labels': labels,
        })
