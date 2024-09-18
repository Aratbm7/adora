from adora.models import Category, Product, Brand, Comment, Car
from adora.serializers import (ProductRetrieveSerializer,
                               ProductListSerializer,
                               BrandSerializer,
                               CommentSerializer,
                               CarSerializer,
                               ProductSearchSerializer,
                               CategoryWhitChildrenSerializer
                               )
# from rest_framework.generics import ListAPIView
from rest_framework.exceptions import PermissionDenied
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
from core.permissions import personal_permissions, object_level_permissions, object_level_permissions_restricted_actions
from django.db.models import Prefetch


class CategoryViewset(ModelViewSet):
    permission_classes = [personal_permissions({'u':3, 'a':63, 'o':3})]
    http_method_names = ['header', 'put', 'post', 'get']
    children_prefetch = Prefetch('children', queryset=Category.objects.all())
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related(children_prefetch)
    serializer_class = CategoryWhitChildrenSerializer
    
    

class ProductViewset(ModelViewSet):
    queryset = Product.objects.select_related(
    'category', 'brand', 
        ).prefetch_related(
    'compatible_cars', 'similar_products', 'images',
        ).all().order_by('id')
    serializer_class = ProductRetrieveSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ProductFilter
    pagination_class = ProductPagination
    permission_classes = [personal_permissions({'u':3, 'a':63, 'o':3})]
        
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
        if (min_price.isdigit() and int(min_price) < 0) or len(min_price)> 20:
            return Response({'error': 'min_price query_param can not be nagative number or more than 20 digits'}, 
                            status=status.HTTP_400_BAD_REQUEST) 
            
        if (max_price.isdigit() and int(max_price) < 0) or len(max_price)> 20:
            return Response({'error': 'max_price queryparam can not be nagative number or more than 20 digits'}, 
                            status=status.HTTP_400_BAD_REQUEST) 
        
        
        return super().list(request, *args, **kwargs)
  
    @action(detail=False, methods=['GET'], url_path='search', permission_classes=[permissions.AllowAny])
    def search(self,request, *args, **kwargs):
        query = request.query_params.get('query', None)
        if query:
            products = Product.objects.filter(fa_name__icontains=query)\
                .select_related( 'category', 'brand', 'material' )\
                    .prefetch_related('images','compatible_cars' )
            serializer = ProductSearchSerializer(products, many=True)
            return Response(serializer.data)
        
        else:
            return Response({'detail': 'Query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)


class BrandViewset(ModelViewSet):
    permission_classes = [personal_permissions({'u':3, 'a':63, 'o':3})]
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


class CarViewset(ModelViewSet):
    http_method_names = ['get']
    permission_classes = [personal_permissions({'u':3, 'a':63, 'o':3})]
    queryset = Car.objects.all()
    serializer_class = CarSerializer


class CommentViewSet(ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [personal_permissions({'u':31, 'a':63, 'o':3}), object_level_permissions_restricted_actions({'u':31,'a':63, 'o': 3})]

    def get_queryset(self):
        if self.action == 'list':
            return Comment.objects.filter(parent__isnull=True).select_related('product', 'user')
        
        # if self.action == 'retrieve':
        #     return Comment.objects.all().select_related('product', 'user')
            
        return Comment.objects.all().select_related('product', 'user')
            

    def perform_create(self, serializer):
        parent_id = self.request.data.get('parent')
        if parent_id:
            parent_comment = Comment.objects.get(id=parent_id)
            serializer.save(user=self.request.user, parent=parent_comment)
        else:
            serializer.save(user=self.request.user)
            
    def perform_update(self, serializer):
        # Ensure the user is automatically assigned from the request
        serializer.save(user=self.request.user)
        
    def perform_destroy(self, instance):
        # Check if the user has permission to delete this comment
        if instance.user != self.request.user:
            raise PermissionDenied("You do not have permission to delete this comment.")
        

    
    
    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        comment = self.get_object()
        serializer = self.get_serializer(comment.get_replies(), many=True)
        return Response(serializer.data)
    