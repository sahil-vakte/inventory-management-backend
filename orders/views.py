from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Sum, Count, Avg, Q, Prefetch
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse
from decimal import Decimal
from .models import Order, OrderItem, OrderStatusHistory, RoyalMailOAuthToken
from .serializers import (
    OrderListSerializer, OrderDetailSerializer, OrderCreateUpdateSerializer,
    OrderListWithItemsSerializer,
    OrderItemSerializer, OrderItemCreateSerializer, OrderStatusHistorySerializer,
    OrderConfirmSerializer, OrderShipSerializer, OrderCancelSerializer,
    OrderStatsSerializer, RoyalMailShipmentSerializer
)
from .services.royal_mail import (
    RoyalMailAPIError,
    RoyalMailClickDropClient,
    RoyalMailConfigError,
    RoyalMailOAuthClient,
    RoyalMailOAuthError,
    extract_royal_mail_reference,
    extract_tracking_number,
)


def _serialize_royal_mail_oauth_token(token):
    if not token:
        return None
    return {
        'connected': bool(token.is_active),
        'token_type': token.token_type,
        'scope': token.scope,
        'expires_at': token.expires_at,
        'is_expired': token.is_expired,
        'needs_refresh': token.needs_refresh,
        'updated_at': token.updated_at,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def royal_mail_oauth_callback(request):
    """Royal Mail redirects here after an admin authorizes WIMS."""
    error = request.query_params.get('error')
    if error:
        return Response(
            {
                'connected': False,
                'error': error,
                'error_description': request.query_params.get('error_description'),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    code = request.query_params.get('code')
    if not code:
        return Response(
            {'connected': False, 'error': 'Royal Mail callback code is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token = RoyalMailOAuthClient().exchange_code(code)
    except RoyalMailConfigError as exc:
        return Response({'connected': False, 'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except RoyalMailOAuthError as exc:
        return Response(
            {
                'connected': False,
                'error': str(exc),
                'royal_mail_status_code': exc.status_code,
                'royal_mail_response': exc.response_data,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({
        'connected': True,
        'message': 'Royal Mail OAuth connected successfully',
        'state': request.query_params.get('state'),
        'token': _serialize_royal_mail_oauth_token(token),
    })


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for Order CRUD operations with soft delete support"""
    
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = [
        'order_status', 'payment_status', 'order_source', 
        'customer_email', 'assigned_to', 'is_deleted',
        'courier_service_name', 'courier_service_code'
    ]
    search_fields = [
        'order_number', 'external_order_id', 'customer_name', 
        'customer_email', 'customer_phone', 'tracking_number',
        'shipping_method', 'carrier', 'courier_service_name', 'courier_service_code'
    ]
    ordering_fields = [
        'order_number', 'order_date', 'total_amount', 'created_at', 
        'customer_name', 'order_status'
    ]
    ordering = ['-order_date', '-created_at']
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        item_queryset = OrderItem.objects.select_related(
            'assigned_to', 'stock_item', 'stock_item__product', 'stock_item__color',
        ).prefetch_related('stock_item__product__extended_data')
        
        if include_deleted == 'true':
            queryset = Order.all_objects.select_related(
                'created_by', 'updated_by', 'assigned_to'
            ).prefetch_related(Prefetch('items', queryset=item_queryset), 'status_history')
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            queryset = Order.all_objects.filter(is_deleted=True).select_related(
                'created_by', 'updated_by', 'assigned_to'
            ).prefetch_related(Prefetch('items', queryset=item_queryset), 'status_history')
        else:
            queryset = Order.objects.select_related(
                'created_by', 'updated_by', 'assigned_to'
            ).prefetch_related(Prefetch('items', queryset=item_queryset), 'status_history')
        
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
        if self.action in ['create', 'update', 'partial_update']:
            return OrderCreateUpdateSerializer
        elif self.action == 'list':
            return OrderListSerializer
        elif self.action in ['confirm', 'label_printed']:
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
    
    @action(detail=True, methods=['post'], url_path='assign-employee')
    def assign_employee(self, request, pk=None):
        """Assign an employee to handle this order"""
        order = self.get_object()
        employee_id = request.data.get('employee_id')
        
        if not employee_id:
            return Response(
                {'error': 'employee_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth.models import User
            employee = User.objects.get(id=employee_id)
            order.assigned_to = employee
            order.updated_by = request.user
            order.save()
            
            return Response({
                'message': f'Order assigned to {employee.username}',
                'order': OrderDetailSerializer(order).data
            })
        except User.DoesNotExist:
            return Response(
                {'error': 'Employee not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'], url_path='unassign-employee')
    def unassign_employee(self, request, pk=None):
        """Unassign employee from order"""
        order = self.get_object()
        order.assigned_to = None
        order.updated_by = request.user
        order.save()
        
        return Response({
            'message': 'Employee unassigned from order',
            'order': OrderDetailSerializer(order).data
        })
    
    @action(detail=False, methods=['get'], url_path='my-assigned-orders')
    def my_assigned_orders(self, request):
        """Get orders assigned to the current user"""
        orders = self.get_queryset().filter(assigned_to=request.user)
        
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='with-items')
    def with_items(self, request):
        """List orders with their nested order items"""
        item_queryset = OrderItem.objects.select_related(
            'assigned_to', 'stock_item', 'stock_item__product', 'stock_item__color',
        ).prefetch_related('stock_item__product__extended_data')
        base_queryset = self.get_queryset().prefetch_related(None)
        orders = self.filter_queryset(
            base_queryset.prefetch_related(Prefetch('items', queryset=item_queryset))
        )

        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = OrderListWithItemsSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = OrderListWithItemsSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """Backward-compatible alias for marking an order label as printed"""
        order = self.get_object()
        serializer = OrderConfirmSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                order.confirm(user=request.user)
                return Response({
                    'message': 'Order label printed successfully',
                    'order': OrderDetailSerializer(order).data
                })
            except ValueError as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='label-printed')
    def label_printed(self, request, pk=None):
        """Mark an order as label printed"""
        order = self.get_object()
        serializer = OrderConfirmSerializer(data=request.data)

        if serializer.is_valid():
            try:
                order.mark_label_printed(user=request.user)
                return Response({
                    'message': 'Order label printed successfully',
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
                    'message': 'Order moved to in progress',
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

    @action(detail=False, methods=['get'], url_path='royal-mail/config')
    def royal_mail_config(self, request):
        """Return Royal Mail Click & Drop configuration status without exposing secrets."""
        active_token = RoyalMailOAuthToken.get_active()
        oauth_connected = bool(active_token and not active_token.is_expired)
        api_key_present = bool(settings.ROYAL_MAIL_API_KEY)
        booking_enabled = api_key_present
        if api_key_present:
            auth_mode = 'api_key'
            message = 'Royal Mail Click & Drop API key is configured.'
        else:
            auth_mode = 'not_configured'
            message = (
                'Set ROYAL_MAIL_API_KEY from Royal Mail Click & Drop '
                'Settings > Integrations > Click & Drop API before booking shipments.'
            )
        return Response({
            'configured': booking_enabled,
            'booking_enabled': booking_enabled,
            'auth_mode': auth_mode,
            'api_base_url': settings.ROYAL_MAIL_API_BASE_URL,
            'auth_url': settings.ROYAL_MAIL_AUTH_URL,
            'username': settings.ROYAL_MAIL_USERNAME,
            'login_credentials_present': bool(settings.ROYAL_MAIL_USERNAME and settings.ROYAL_MAIL_PASSWORD),
            'default_package_format': settings.ROYAL_MAIL_DEFAULT_PACKAGE_FORMAT,
            'default_weight_grams': settings.ROYAL_MAIL_DEFAULT_WEIGHT_GRAMS,
            'api_key_present': api_key_present,
            'api_key_required_for_booking': True,
            'oauth_client_id_present': bool(settings.ROYAL_MAIL_CLIENT_ID),
            'oauth_client_secret_present': bool(settings.ROYAL_MAIL_CLIENT_SECRET),
            'oauth_callback_url': settings.ROYAL_MAIL_OAUTH_CALLBACK_URL,
            'oauth_authorization_url': settings.ROYAL_MAIL_OAUTH_AUTHORIZATION_URL,
            'oauth_token_url_present': bool(settings.ROYAL_MAIL_OAUTH_TOKEN_URL),
            'oauth_connected': oauth_connected,
            'oauth_used_for_booking': False,
            'oauth_token': _serialize_royal_mail_oauth_token(active_token),
            'message': message,
        })

    @action(detail=False, methods=['get'], url_path='royal-mail/oauth/start')
    def royal_mail_oauth_start(self, request):
        """Return the Royal Mail authorization URL for connecting the account."""
        if not settings.ROYAL_MAIL_OAUTH_AUTHORIZATION_URL or not settings.ROYAL_MAIL_OAUTH_TOKEN_URL:
            return Response({
                'error': 'Royal Mail OAuth is not configured for this project.',
                'message': (
                    'Current Royal Mail implementation uses Option 1: Click & Drop API key. '
                    'Set ROYAL_MAIL_API_KEY and use /api/v1/orders/{order_id}/book-royal-mail-shipping/.'
                ),
                'required_setting': 'ROYAL_MAIL_API_KEY',
                'config_url': '/api/v1/orders/royal-mail/config/',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            authorization_url = RoyalMailOAuthClient().build_authorization_url(
                state=request.query_params.get('state')
            )
        except RoyalMailConfigError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'authorization_url': authorization_url,
            'callback_url': settings.ROYAL_MAIL_OAUTH_CALLBACK_URL,
            'client_id_present': bool(settings.ROYAL_MAIL_CLIENT_ID),
            'client_secret_present': bool(settings.ROYAL_MAIL_CLIENT_SECRET),
        })

    @action(detail=False, methods=['get'], url_path='royal-mail/oauth/status')
    def royal_mail_oauth_status(self, request):
        """Return Royal Mail OAuth connection status without exposing tokens."""
        active_token = RoyalMailOAuthToken.get_active()
        return Response({
            'connected': bool(active_token and not active_token.is_expired),
            'client_id_present': bool(settings.ROYAL_MAIL_CLIENT_ID),
            'client_secret_present': bool(settings.ROYAL_MAIL_CLIENT_SECRET),
            'callback_url': settings.ROYAL_MAIL_OAUTH_CALLBACK_URL,
            'token': _serialize_royal_mail_oauth_token(active_token),
        })

    @action(detail=False, methods=['post'], url_path='royal-mail/oauth/disconnect')
    def royal_mail_oauth_disconnect(self, request):
        """Deactivate saved Royal Mail OAuth tokens."""
        updated = RoyalMailOAuthToken.objects.filter(is_active=True).update(is_active=False)
        return Response({
            'message': 'Royal Mail OAuth disconnected',
            'tokens_deactivated': updated,
            'connected': False,
        })

    @action(detail=True, methods=['post'], url_path='book-royal-mail-shipping')
    def book_royal_mail_shipping(self, request, pk=None):
        """Create this order in Royal Mail Click & Drop and mark it shipped."""
        order = self.get_object()
        serializer = RoyalMailShipmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            response_data = RoyalMailClickDropClient().create_order(
                order,
                weight_in_grams=serializer.validated_data.get('weight_in_grams'),
                package_format_identifier=serializer.validated_data.get('package_format_identifier') or None,
                service_code=serializer.validated_data.get('service_code') or None,
            )
            tracking_number = extract_tracking_number(response_data)
            royal_mail_reference = order.external_order_id or extract_royal_mail_reference(response_data)

            note_parts = ['Royal Mail Click & Drop shipment booked.']
            if royal_mail_reference:
                note_parts.append(f'Reference: {royal_mail_reference}.')
            if serializer.validated_data.get('notes'):
                note_parts.append(serializer.validated_data['notes'])
            note = ' '.join(note_parts)
            order.internal_notes = f"{order.internal_notes}\n{note}".strip() if order.internal_notes else note
            if serializer.validated_data.get('service_code'):
                order.shipping_method = serializer.validated_data['service_code']
            order.save(update_fields=['internal_notes', 'shipping_method', 'updated_at'])

            order.mark_shipped(
                tracking_number=tracking_number,
                carrier='Royal Mail',
                user=request.user,
            )
        except RoyalMailConfigError as exc:
            return Response({
                'error': str(exc),
                'message': (
                    'Generate a Click & Drop API authorisation key from Royal Mail '
                    'Settings > Integrations > Click & Drop API and set ROYAL_MAIL_API_KEY.'
                ),
                'auth_url': settings.ROYAL_MAIL_AUTH_URL,
                'username': settings.ROYAL_MAIL_USERNAME,
            }, status=status.HTTP_400_BAD_REQUEST)
        except RoyalMailAPIError as exc:
            return Response(
                {
                    'error': str(exc),
                    'royal_mail_status_code': exc.status_code,
                    'royal_mail_response': exc.response_data,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except RoyalMailOAuthError as exc:
            return Response(
                {
                    'error': str(exc),
                    'royal_mail_status_code': exc.status_code,
                    'royal_mail_response': exc.response_data,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': 'Royal Mail shipment booked and order marked as shipped',
            'tracking_number': tracking_number,
            'royal_mail_reference': royal_mail_reference,
            'royal_mail_response': response_data,
            'order': OrderDetailSerializer(order).data,
        })
    
    @action(detail=True, methods=['post'], url_path='deliver')
    def deliver(self, request, pk=None):
        """Deprecated: delivered status was replaced by shipped"""
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
        
        if order.order_status not in [Order.STATUS_NEW, Order.STATUS_LABEL_PRINTED]:
            return Response(
                {'error': 'Cannot add items unless order is New or Label Printed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OrderItemCreateSerializer(data=request.data)
        if serializer.is_valid():
            item = serializer.save(order=order)
            
            # Note: Stock must be reserved manually by assigned employee
            # Stock is not automatically reserved to allow for flexibility
            
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
        
        if order.order_status not in [Order.STATUS_NEW, Order.STATUS_LABEL_PRINTED]:
            return Response(
                {'error': 'Cannot remove items unless order is New or Label Printed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            item = order.items.get(id=item_id)
            # Note: Stock must be released manually by assigned employee
            # Stock is not automatically released to allow for flexibility
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

    @action(detail=True, methods=['patch'], url_path='items/(?P<item_id>[^/.]+)/lable-printed')
    def update_item_lable_printed(self, request, pk=None, item_id=None):
        """Update label printed flag for one or more items inside this order."""
        order = self.get_object()
        return self._update_order_items_lable_printed(order, request.data, fallback_item_ids=item_id)

    @action(detail=True, methods=['patch'], url_path='items/lable-printed')
    def bulk_update_items_lable_printed(self, request, pk=None):
        """Update label printed flag for multiple items inside this order."""
        order = self.get_object()
        return self._update_order_items_lable_printed(order, request.data)

    @action(detail=False, methods=['patch'], url_path='items/lable-printed')
    def bulk_update_any_items_lable_printed(self, request):
        """Update label printed flag for multiple order items by item ids."""
        return self._update_order_items_lable_printed(None, request.data)

    def _update_order_items_lable_printed(self, order, payload, fallback_item_ids=None):
        value = payload.get('lable_printed', True)
        raw_ids = payload.get('order_item_ids') or fallback_item_ids

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized not in {'true', 'false', '1', '0', 'yes', 'no'}:
                return Response(
                    {'error': 'lable_printed must be a boolean'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            value = normalized in {'true', '1', 'yes'}
        else:
            value = bool(value)

        if isinstance(raw_ids, str):
            raw_ids = [part.strip() for part in raw_ids.split(',') if part.strip()]
        elif isinstance(raw_ids, (list, tuple)):
            raw_ids = list(raw_ids)
        else:
            raw_ids = [raw_ids]

        try:
            item_ids = [int(raw_id) for raw_id in raw_ids]
        except (TypeError, ValueError):
            return Response(
                {'error': 'order item ids must be integers'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item_ids = list(dict.fromkeys(item_ids))
        if not item_ids:
            return Response(
                {'error': 'At least one order item id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_queryset = order.items if order is not None else OrderItem.objects
        items = list(
            base_queryset.select_related(
                'order', 'stock_item', 'stock_item__product', 'stock_item__color', 'assigned_to',
            ).prefetch_related('stock_item__product__extended_data').filter(id__in=item_ids).order_by('id')
        )
        found_ids = {item.id for item in items}
        missing_ids = [item_id for item_id in item_ids if item_id not in found_ids]
        if missing_ids:
            error_message = (
                'Some items were not found for this order'
                if order is not None else
                'Some order items were not found'
            )
            return Response(
                {
                    'error': error_message,
                    'missing_order_item_ids': missing_ids,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        for item in items:
            item.lable_printed = value
            item.save(update_fields=['lable_printed', 'updated_at'])

        serialized_items = OrderItemSerializer(items, many=True).data

        response_data = {
            'message': 'Item label printed flag updated successfully',
            'updated_count': len(items),
            'item': serialized_items[0] if len(serialized_items) == 1 else None,
            'items': serialized_items,
        }
        if order is not None:
            order.refresh_from_db()
            response_data['order'] = OrderDetailSerializer(order).data
        else:
            response_data['order_ids'] = sorted({item.order_id for item in items})

        return Response(response_data)
    
    @action(detail=False, methods=['get'], url_path='statuses', permission_classes=[])
    def statuses(self, request):
        """Return all status choices for orders and order items"""
        return Response({
            'order_statuses': [
                {'value': v, 'label': l} for v, l in Order.STATUS_CHOICES
            ],
            'payment_statuses': [
                {'value': v, 'label': l} for v, l in Order.PAYMENT_STATUS_CHOICES
            ],
            'order_sources': [
                {'value': v, 'label': l} for v, l in Order.SOURCE_CHOICES
            ],
            'item_processing_statuses': [
                {'value': v, 'label': l} for v, l in OrderItem.ITEM_STATUS_CHOICES
            ],
        })

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Get order statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_orders': queryset.count(),
            'new_orders': queryset.filter(order_status=Order.STATUS_NEW).count(),
            'label_printed_orders': queryset.filter(order_status=Order.STATUS_LABEL_PRINTED).count(),
            'in_progress_orders': queryset.filter(order_status=Order.STATUS_IN_PROGRESS).count(),
            'completed_orders': queryset.filter(order_status=Order.STATUS_COMPLETED).count(),
            'shipped_orders': queryset.filter(order_status=Order.STATUS_SHIPPED).count(),
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

    @action(detail=False, methods=['get'], url_path='label-excel')
    def label_excel(self, request):
        """Export one label row per order item with the WIMS courier code."""
        try:
            from openpyxl import Workbook
        except ImportError:
            return Response(
                {'error': 'openpyxl is required to export order label Excel files'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        item_queryset = OrderItem.objects.select_related(
            'stock_item', 'stock_item__product', 'stock_item__color', 'assigned_to',
        ).prefetch_related('stock_item__product__extended_data')
        base_queryset = self.get_queryset().prefetch_related(None)
        queryset = self.filter_queryset(
            base_queryset.prefetch_related(Prefetch('items', queryset=item_queryset))
        )

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = 'Order Labels'
        headers = [
            'Order ID',
            'Order Number',
            'External Order ID',
            'Order Date',
            'Customer Name',
            'SKU',
            'Product Name',
            'Quantity',
            'Courier Service',
            'Courier Code',
            'Shipping Method',
            'Carrier',
        ]
        worksheet.append(headers)

        for order in queryset:
            order_date = ''
            if order.order_date:
                order_date = timezone.localtime(order.order_date).strftime('%Y-%m-%d %H:%M:%S')
            for item in order.items.all():
                worksheet.append([
                    order.id,
                    order.order_number,
                    order.external_order_id or '',
                    order_date,
                    order.customer_name,
                    item.sku,
                    item.product_name,
                    item.quantity,
                    order.courier_service_name or '',
                    order.courier_service_code or '',
                    order.shipping_method or '',
                    order.carrier or '',
                ])

        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value or '')) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 40)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        timestamp = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="order_label_export_{timestamp}.xlsx"'
        workbook.save(response)
        return response
    
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

    @action(detail=False, methods=['get'], url_path='import_from_remote_tiaknightfabrics')
    def import_from_remote_tiaknightfabrics(self, request):
        """Fetch orders from remote Tiaknight SOAP service and import into DB.

        Uses a pure requests-based SOAP client (no browser/Playwright needed).
        Handles the anti-bot interstitial via session cookies. Extracts the
        orders XML from the SOAP <Result> value, and feeds it through the SAME
        parse_and_create_orders logic that upload-xml uses. Duplicates are
        skipped automatically.

        GET {{base_url}}/api/v1/orders/import-from-remote/
        Auth: Bearer Token (JWT)
        """
        try:
            from .services.remote_tiaknight_import import (
                RemoteTiaknightConfigError,
                RemoteTiaknightFetchError,
                RemoteTiaknightParseError,
                import_remote_tiaknight_orders,
            )
            result = import_remote_tiaknight_orders(user=getattr(request, 'user', None))
        except RemoteTiaknightConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RemoteTiaknightFetchError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except RemoteTiaknightParseError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        resp_status = status.HTTP_201_CREATED if result['created_count'] > 0 else status.HTTP_200_OK
        return Response({
            'message': 'Import from remote completed',
            'orders_created': result['created_count'],
            'orders_failed':  result['failed_count'],
            'orders':  result['orders'],
            'errors':  result['errors'],
            'orders_received_from_tiaknight': result.get('received_order_refs_count', 0),
            'tiaknight_order_refs': result.get('received_order_refs', []),
            'tiaknight_request_id': result.get('tiaknight_request_id'),
            'tiaknight_source_datetime': result.get('tiaknight_source_datetime'),
            'tiaknight_auto_update': result.get('tiaknight_auto_update'),
            'tiaknight_audit_log': result.get('tiaknight_audit_log_path'),
            'tiaknight_raw_payload': result.get('tiaknight_raw_payload_path'),
        }, status=resp_status)


class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for order items"""
    
    queryset = OrderItem.objects.select_related(
        'assigned_to', 'order', 'stock_item', 'stock_item__product', 'stock_item__color',
    ).prefetch_related('stock_item__product__extended_data').all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['order', 'sku', 'processing_status', 'assigned_to']
    search_fields = ['sku', 'product_name']
    ordering_fields = ['created_at', 'quantity', 'line_total']
    ordering = ['-created_at']

    @action(detail=True, methods=['patch'], url_path='assign')
    def assign(self, request, pk=None):
        """Assign or unassign an employee to this order item"""
        item = self.get_object()
        employee_id = request.data.get('assigned_to')

        if employee_id is None:
            item.assigned_to = None
            item.save(update_fields=['assigned_to', 'updated_at'])
            return Response({
                'id': item.id,
                'sku': item.sku,
                'order_number': item.order.order_number,
                'assigned_to': None,
                'assigned_to_username': None,
                'message': 'Item unassigned successfully',
            })

        from django.contrib.auth.models import User as AuthUser
        try:
            employee = AuthUser.objects.get(pk=employee_id)
        except AuthUser.DoesNotExist:
            return Response(
                {'error': f'User with id {employee_id} does not exist'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item.assigned_to = employee
        item.save(update_fields=['assigned_to', 'updated_at'])
        return Response({
            'id': item.id,
            'sku': item.sku,
            'order_number': item.order.order_number,
            'assigned_to': employee.id,
            'assigned_to_username': employee.username,
            'assigned_to_full_name': employee.get_full_name(),
            'message': f'Item assigned to {employee.username}',
        })

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        """Update the processing status of an order item"""
        item = self.get_object()
        new_status = request.data.get('processing_status')
        quantity_processed = request.data.get('quantity_processed')

        if new_status is None:
            return Response(
                {'error': 'processing_status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_statuses = [s[0] for s in OrderItem.ITEM_STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status "{new_status}"', 'valid_statuses': valid_statuses},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity_processed is not None:
            try:
                quantity_processed = int(quantity_processed)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'quantity_processed must be an integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if quantity_processed < 0 or quantity_processed > item.quantity:
                return Response(
                    {'error': f'quantity_processed must be between 0 and {item.quantity}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            item.quantity_processed = quantity_processed
        elif new_status in [OrderItem.ITEM_STATUS_PICKED, OrderItem.ITEM_STATUS_COMPLETED]:
            item.quantity_processed = item.quantity
        elif new_status == OrderItem.ITEM_STATUS_PENDING:
            item.quantity_processed = 0

        old_status = item.processing_status
        item.processing_status = new_status
        item.save(update_fields=['processing_status', 'quantity_processed', 'updated_at'])
        order_status_changed = item.order.sync_status_with_completion(user=request.user)
        item.order.refresh_from_db()

        return Response({
            'id': item.id,
            'sku': item.sku,
            'order_number': item.order.order_number,
            'order_status': item.order.order_status,
            'order_status_display': item.order.get_order_status_display(),
            'order_status_changed': order_status_changed,
            'order_completion_percentage': item.order.get_completion_percentage(),
            'previous_status': old_status,
            'processing_status': item.processing_status,
            'processing_status_display': item.get_processing_status_display(),
            'quantity': item.quantity,
            'quantity_processed': item.quantity_processed,
            'completion_pct': round((item.quantity_processed / item.quantity) * 100) if item.quantity else 0,
        })


class OrderStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for order status history"""
    
    queryset = OrderStatusHistory.objects.all()
    serializer_class = OrderStatusHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    
    filterset_fields = ['order', 'from_status', 'to_status', 'changed_by']
    ordering = ['-timestamp']
