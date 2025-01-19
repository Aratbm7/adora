from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class ProductPagination(PageNumberPagination):
    page_size = 20
    page_query_param = 'page'
    
    # def get_paginated_response(self, data):
    #     return Response(data)