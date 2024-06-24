from django_filters import rest_framework as filters
from adora.models import Product
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseBadRequest
class ProductFilter(filters.FilterSet):
    
    min_price = filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = filters.NumberFilter(field_name="price", lookup_expr='lte')
    # min_price = filters.NumberFilter(field_name="price", lookup_expr='gte', method='filter_min_price')
    # max_price = filters.NumberFilter(field_name="price", lookup_expr='lte', method='filter_max_price')

    class Meta:
        model = Product
        fields = ['category', 'brand','compatible_cars', 'new', 'count']

    # def filter_min_price(self, queryset, name, value):
    #     try:
    #         print('sadfsdkaljlddodddddddddddddddd')
    #         return queryset.filter(**{f'{name}__gte': int(value)})
    #     except ValidationError as e:
    #         # Handle validation error for min_price
    #         # You can log the error or return a custom response
    #         print('how are you ')
    #         return queryset.none()  # Return an empty queryset or handle the error accordingly

    # def filter_max_price(self, queryset, name, value):
    #     try:
    #         if len(str(value)) > 15:  # Example: Limit to 15 digits
    #             return HttpResponseBadRequest(
    #                 content=JsonResponse({'error': f'Bad Request: Max price value for {name} is too long'}, status=400)
    #             )
            
    #         max_price = int(value)
    #         return queryset.filter(price__lte=max_price)
    #     except ValueError:
    #         return HttpResponseBadRequest(
    #             content=JsonResponse({'error': f'Bad Request: Invalid max price value for {name}'}, status=400)
    #         )