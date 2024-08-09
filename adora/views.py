from adora.models import Category, Product, Brand, Comment
from adora.serializers import (ProductRetrieveSerializer,
                               ProductListSerializer,
                               CategorySerializer,
                               BrandSerializer,
                               CommentSerializer
                               )
# from rest_framework.generics import ListAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from django_filters import rest_framework as filters
from adora.filters import ProductFilter
from rest_framework.response import Response
from adora.paginations import ProductPagination
from drf_yasg.utils import swagger_auto_schema, swagger_serializer_method
from drf_yasg import openapi
from typing import Optional, Dict
from rest_framework.decorators import action
from rest_framework import permissions

class CategoryViewset(ModelViewSet):
    http_method_names = ['header', 'put', 'post', 'get']
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    
    
    
class ProductViewset(ModelViewSet):
    queryset = Product.objects.select_related(
    'category', 'brand', 'material'
        ).prefetch_related(
    'compatible_cars', 'similar_products', 'images'
        ).all().order_by('id')
    serializer_class = ProductRetrieveSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ProductFilter
    pagination_class = ProductPagination
    
        
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = ProductRetrieveSerializer   
        return super().retrieve(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="لیست محصولات را به صورت ۲۰ تا ۲۰ تا برمیگرداند.",
        # manual_parameters=[
        #     openapi.Parameter(
        #         'author', 
        #         openapi.IN_QUERY, 
        #         description="Filter books by author name", 
        #         type=openapi.TYPE_STRING
        #     ),
        #     openapi.Parameter(
        #         'published_date', 
        #         openapi.IN_QUERY, 
        #         description="Filter books by published date (YYYY-MM-DD)", 
        #         type=openapi.TYPE_STRING
        #     ),
        #     openapi.Parameter(
        #         'title', 
        #         openapi.IN_QUERY, 
        #         description="Filter books by title", 
        #         type=openapi.TYPE_STRING
        #     ),
        # ],
        responses={200: ProductRetrieveSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        query_params = request.query_params
        min_price = query_params.get('min_price', '')
        max_price = query_params.get('max_price', '')
        
        self.serializer_class = ProductListSerializer 
        if (min_price.isdigit() and int(min_price) < 0) or len(min_price)> 12:
            return Response({'error': 'min_price query_param can not be nagative number or more than 12 digits'}, 
                            status=status.HTTP_400_BAD_REQUEST) 
            
        if (max_price.isdigit() and int(max_price) < 0) or len(max_price)> 12:
            return Response({'error': 'max_price queryparam can not be nagative number or more than 12 digits'}, 
                            status=status.HTTP_400_BAD_REQUEST) 
        
        
        return super().list(request, *args, **kwargs)
  
    


class BrandViewset(ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


class CommentViewSet(ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    def get_queryset(self):
        return Comment.objects.filter(parent__isnull=True).select_related('product')\
            .select_related('user')

    def perform_create(self, serializer):
        parent_id = self.request.data.get('parent')
        if parent_id:
            parent_comment = Comment.objects.get(id=parent_id)
            serializer.save(parent=parent_comment)
        else:
            serializer.save()
    
    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        comment = self.get_object()
        serializer = self.get_serializer(comment.get_replies(), many=True)
        return Response(serializer.data)