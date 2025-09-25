from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
import pandas as pd
from django.db import transaction
from .models import Color
from .serializers import ColorSerializer, ColorListSerializer, ColorCreateUpdateSerializer

class ColorViewSet(viewsets.ModelViewSet):
    """ViewSet for Color CRUD operations with soft delete support"""
    queryset = Color.objects.all()  # Default queryset for router registration
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_deleted']
    search_fields = ['color_code', 'color_name']
    ordering_fields = ['color_code', 'color_name', 'created_at']
    ordering = ['color_code']
    
    def get_queryset(self):
        """Return queryset based on include_deleted parameter"""
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower()
        if include_deleted == 'true':
            return Color.all_objects.all()
        elif self.request.query_params.get('only_deleted', 'false').lower() == 'true':
            return Color.all_objects.filter(is_deleted=True)
        else:
            return Color.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ColorListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ColorCreateUpdateSerializer
        return ColorSerializer
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to perform soft delete by default"""
        instance = self.get_object()
        force_delete = request.query_params.get('force_delete', 'false').lower() == 'true'
        
        if force_delete:
            # Permanent delete
            instance.hard_delete()
            return Response(
                {'message': 'Color permanently deleted'}, 
                status=status.HTTP_204_NO_CONTENT
            )
        else:
            # Soft delete
            instance.soft_delete()
            return Response(
                {'message': 'Color soft deleted'}, 
                status=status.HTTP_200_OK
            )
    
    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted color"""
        try:
            color = Color.all_objects.get(color_code=pk)
            if not color.is_deleted:
                return Response(
                    {'error': 'Color is not deleted'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            color.restore()
            serializer = self.get_serializer(color)
            return Response({
                'message': 'Color restored successfully',
                'data': serializer.data
            })
        except Color.DoesNotExist:
            return Response(
                {'error': 'Color not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'], url_path='import-excel')
    def import_excel(self, request):
        """Import colors from Excel file"""
        try:
            if 'file' not in request.FILES:
                return Response(
                    {'error': 'No file provided'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            file = request.FILES['file']
            
            # Validate file type
            if not file.name.endswith(('.xlsx', '.xls')):
                return Response(
                    {'error': 'File must be Excel format (.xlsx or .xls)'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Read Excel file
            try:
                df = pd.read_excel(file, sheet_name='Colours')
            except Exception as e:
                return Response(
                    {'error': f'Error reading Excel file: {str(e)}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required columns
            required_columns = ['ColorCode', 'ColorName']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return Response(
                    {'error': f'Missing required columns: {missing_columns}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Import data
            created_count = 0
            updated_count = 0
            errors = []
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        color_code = str(row['ColorCode']).strip()
                        color_name = str(row['ColorName']).strip()
                        
                        if pd.isna(row['ColorCode']) or pd.isna(row['ColorName']):
                            continue
                        
                        # Get or create color
                        color, created = Color.objects.get_or_create(
                            color_code=color_code,
                            defaults={
                                'color_name': color_name,
                                'secondary_code': str(row.get('Unnamed: 2', '')).strip() if not pd.isna(row.get('Unnamed: 2')) else None
                            }
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            # Update existing
                            color.color_name = color_name
                            if not pd.isna(row.get('Unnamed: 2')):
                                color.secondary_code = str(row.get('Unnamed: 2', '')).strip()
                            color.save()
                            updated_count += 1
                            
                    except Exception as e:
                        errors.append(f"Row {index + 1}: {str(e)}")
            
            return Response({
                'message': 'Import completed successfully',
                'created': created_count,
                'updated': updated_count,
                'errors': errors
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Unexpected error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='export-excel')
    def export_excel(self, request):
        """Export colors to Excel file"""
        try:
            colors = Color.objects.all()
            data = []
            
            for color in colors:
                data.append({
                    'ColorCode': color.color_code,
                    'ColorName': color.color_name,
                    'SecondaryCode': color.secondary_code or '',
                    'CreatedAt': color.created_at,
                    'UpdatedAt': color.updated_at
                })
            
            df = pd.DataFrame(data)
            
            # Create Excel response
            from django.http import HttpResponse
            from io import BytesIO
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Colors', index=False)
            
            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="colors_export.xlsx"'
            
            return response
            
        except Exception as e:
            return Response(
                {'error': f'Export failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
