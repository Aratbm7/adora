from django_filters import rest_framework as filters
from adora.models import Product, Category
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseBadRequest
class ProductFilter(filters.FilterSet):
    
    min_price = filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = filters.NumberFilter(field_name="price", lookup_expr='lte')
    count = filters.NumberFilter(field_name="count", lookup_expr='gte')
    discounter_products = filters.NumberFilter(field_name='price_discount_percent', lookup_expr='gte')
    category = filters.NumberFilter(method='filter_by_category')

    # min_price = filters.NumberFilter(field_name="price", lookup_expr='gte', method='filter_min_price')
    # max_price = filters.NumberFilter(field_name="price", lookup_expr='lte', method='filter_max_price')


    def filter_by_category(self, queryset, name, value):
        try:
            # Fetch the category and its descendants
            category = Category.objects.get(id=value)
            categories = [category] + category.get_descendants()
            category_ids = [cat.id for cat in categories]
            return queryset.filter(category__id__in=category_ids)
        except Category.DoesNotExist:
            return queryset.none()  # Return no results if category does not exist
    

    class Meta:
        model = Product
        fields = ['category','compatible_cars', 'brand','compatible_cars', 'new', 'count', 'best_seller']

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
