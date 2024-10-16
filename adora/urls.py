from django.urls import path, include
from rest_framework.routers import DefaultRouter
from adora.views import (CategoryViewset,
                         ProductViewset,
                         BrandViewset,
                         CommentViewSet,
                         CarViewset,
                         OrderViewSet)

router = DefaultRouter()

router.register('categories', CategoryViewset, basename="categories")
router.register('products', ProductViewset, basename="products")
router.register('brands', BrandViewset, basename="brands")
router.register('cars', CarViewset, basename="cars")
router.register('comments', CommentViewSet, basename="comments")
router.register('orders', OrderViewSet, basename="orders")


urlpatterns = [
    path('', include(router.urls)),
]