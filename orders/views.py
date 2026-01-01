from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from decimal import Decimal
from .models import Order, OrderItem, OrderStatusHistory
from .serializers import (
    OrderListSerializer, OrderDetailSerializer, OrderCreateUpdateSerializer,
    OrderItemSerializer, OrderItemCreateSerializer, OrderStatusHistorySerializer,
    OrderConfirmSerializer, OrderShipSerializer, OrderCancelSerializer,
    OrderStatsSerializer
)


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for Order CRUD operations with soft delete support"""
    
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = [
        'order_status', 'payment_status', 'order_source', 
        'customer_email', 'is_deleted'
    ]
    search_fields = [
        'order_number', 'external_order_id', 'customer_name', 
        'customer_email', 'customer_phone', 'tracking_number'
    ]
    ordering_fields = [
        'order_number', 'order_date', 'total_amount', 'created_at', 
        'customer_name', 'order_status'
    ]
    ordering = ['-order_date', '-created_at']
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        
        if include_deleted == 'true':
            queryset = Order.all_objects.select_related(
                'created_by', 'updated_by'
            ).prefetch_related('items', 'status_history')
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            queryset = Order.all_objects.filter(is_deleted=True).select_related(
                'created_by', 'updated_by'
            ).prefetch_related('items', 'status_history')
        else:
            queryset = Order.objects.select_related(
                'created_by', 'updated_by'
            ).prefetch_related('items', 'status_history')
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(order_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(order_date__lte=date_to)
        
        # Filter by total amount range
        min_total = self.request.query_params.get('min_total')
        max_total = self.request.query_params.get('max_total')
        
        if min_total:
            queryset = queryset.filter(total_amount__gte=min_total)
        if max_total:
            queryset = queryset.filter(total_amount__lte=max_total)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return OrderListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return OrderCreateUpdateSerializer
        elif self.action == 'confirm':
            return OrderConfirmSerializer
        elif self.action == 'ship':
            return OrderShipSerializer
        elif self.action == 'cancel':
            return OrderCancelSerializer
        return OrderDetailSerializer
    
    def perform_create(self, serializer):
        """Set created_by when creating an order"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating an order"""
        serializer.save(updated_by=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to perform soft delete by default"""
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        
        if force_delete:
            instance.hard_delete()
            return Response(
                {'message': 'Order permanently deleted'}, 
                status=status.HTTP_204_NO_CONTENT
            )
        else:
            instance.soft_delete(user=request.user)
            return Response(
                {'message': 'Order soft deleted'}, 
                status=status.HTTP_200_OK
            )
    
    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted order"""
        try:
            order = Order.all_objects.get(id=pk)
            if not order.is_deleted:
                return Response(
                    {'error': 'Order is not deleted'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order.restore()
            serializer = self.get_serializer(order)
            return Response({
                'message': 'Order restored successfully', 
                'data': serializer.data
            })
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """Confirm an order"""
        order = self.get_object()
        serializer = OrderConfirmSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                order.confirm(user=request.user)
                return Response({
                    'message': 'Order confirmed successfully',
                    'order': OrderDetailSerializer(order).data
                })
            except ValueError as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='start-processing')
    def start_processing(self, request, pk=None):
        """Start processing an order"""
        order = self.get_object()
        
        try:
            order.start_processing(user=request.user)
            return Response({
                'message': 'Order processing started',
                'order': OrderDetailSerializer(order).data
            })
        except ValueError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='ship')
    def ship(self, request, pk=None):
        """Mark an order as shipped"""
        order = self.get_object()
        serializer = OrderShipSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                order.mark_shipped(
                    tracking_number=serializer.validated_data.get('tracking_number'),
                    carrier=serializer.validated_data.get('carrier'),
                    user=request.user
                )
                return Response({
                    'message': 'Order marked as shipped',
                    'order': OrderDetailSerializer(order).data
                })
            except ValueError as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='deliver')
    def deliver(self, request, pk=None):
        """Mark an order as delivered"""
        order = self.get_object()
        
        try:
            order.mark_delivered(user=request.user)
            return Response({
                'message': 'Order marked as delivered',
                'order': OrderDetailSerializer(order).data
            })
        except ValueError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel an order"""
        order = self.get_object()
        serializer = OrderCancelSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                order.cancel(
                    reason=serializer.validated_data.get('reason'),
                    user=request.user
                )
                return Response({
                    'message': 'Order cancelled successfully',
                    'order': OrderDetailSerializer(order).data
                })
            except ValueError as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='add-item')
    def add_item(self, request, pk=None):
        """Add an item to an existing order"""
        order = self.get_object()
        
        if order.order_status not in [Order.STATUS_PENDING, Order.STATUS_CONFIRMED]:
            return Response(
                {'error': 'Cannot add items to order in current status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OrderItemCreateSerializer(data=request.data)
        if serializer.is_valid():
            item = serializer.save(order=order)
            
            # Reserve stock
            if item.stock_item:
                try:
                    item.reserve_stock()
                except Exception as e:
                    return Response(
                        {'error': f'Failed to reserve stock: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Recalculate order totals
            order.calculate_totals()
            order.save()
            
            return Response({
                'message': 'Item added successfully',
                'item': OrderItemSerializer(item).data,
                'order': OrderDetailSerializer(order).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        """Remove an item from an order"""
        order = self.get_object()
        
        if order.order_status not in [Order.STATUS_PENDING, Order.STATUS_CONFIRMED]:
            return Response(
                {'error': 'Cannot remove items from order in current status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            item = order.items.get(id=item_id)
            item.release_stock()
            item.delete()
            
            # Recalculate order totals
            order.calculate_totals()
            order.save()
            
            return Response({
                'message': 'Item removed successfully',
                'order': OrderDetailSerializer(order).data
            })
        except OrderItem.DoesNotExist:
            return Response(
                {'error': 'Item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Get order statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_orders': queryset.count(),
            'pending_orders': queryset.filter(order_status=Order.STATUS_PENDING).count(),
            'confirmed_orders': queryset.filter(order_status=Order.STATUS_CONFIRMED).count(),
            'processing_orders': queryset.filter(order_status=Order.STATUS_PROCESSING).count(),
            'shipped_orders': queryset.filter(order_status=Order.STATUS_SHIPPED).count(),
            'delivered_orders': queryset.filter(order_status=Order.STATUS_DELIVERED).count(),
            'cancelled_orders': queryset.filter(order_status=Order.STATUS_CANCELLED).count(),
        }
        
        # Financial stats
        financial = queryset.aggregate(
            total_revenue=Sum('total_amount'),
            average_order_value=Avg('total_amount')
        )
        
        stats['total_revenue'] = financial['total_revenue'] or Decimal('0.00')
        stats['average_order_value'] = financial['average_order_value'] or Decimal('0.00')
        
        # Unpaid orders
        unpaid = queryset.filter(
            payment_status__in=[Order.PAYMENT_UNPAID, Order.PAYMENT_PARTIAL]
        ).aggregate(
            count=Count('id'),
            total=Sum('total_amount')
        )
        
        stats['unpaid_orders_count'] = unpaid['count'] or 0
        stats['unpaid_orders_value'] = unpaid['total'] or Decimal('0.00')
        
        serializer = OrderStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='upload-xml')
    def upload_xml(self, request):
        """Upload orders from XML file"""
        from .services.xml_parser import XMLOrderParser
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        xml_file = request.FILES['file']
        
        try:
            parser = XMLOrderParser()
            result = parser.parse_and_create_orders(xml_file, user=request.user)
            
            return Response({
                'message': 'XML processed successfully',
                'orders_created': result['created_count'],
                'orders_failed': result['failed_count'],
                'orders': result['orders'],
                'errors': result['errors']
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': f'Failed to process XML: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for order items"""
    
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['order', 'sku', 'stock_reserved', 'stock_fulfilled']
    search_fields = ['sku', 'product_name']
    ordering_fields = ['created_at', 'quantity', 'line_total']
    ordering = ['-created_at']


class OrderStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for order status history"""
    
    queryset = OrderStatusHistory.objects.all()
    serializer_class = OrderStatusHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    
    filterset_fields = ['order', 'from_status', 'to_status', 'changed_by']
    ordering = ['-timestamp']
