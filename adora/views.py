from django.shortcuts import render
from adora.models import Category, Product, Brand
from adora.serializers import ProductRetrieveSerializer,ProductListSerializer,  CategorySerializer, BrandSerializer
# from rest_framework.generics import ListAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from django_filters import rest_framework as filters
from adora.filters import ProductFilter
from rest_framework.response import Response
from adora.paginations import ProductPagination



class CategoryViewset(ModelViewSet):
    http_method_names = ['header', 'put', 'post', 'get']
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    
    
    
class ProductViewset(ModelViewSet):
    queryset = Product.objects.select_related(
    'category', 'brand', 'material'
        ).prefetch_related(
    'compatible_cars', 'similar_products', 'images'
        ).all()
    serializer_class = ProductRetrieveSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ProductFilter
    pagination_class = ProductPagination
    
        
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = ProductRetrieveSerializer   
        return super().retrieve(request, *args, **kwargs)
    
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
    