from django.urls import path, include
from rest_framework.routers import DefaultRouter
from adora.views import CategoryViewset, ProductViewset, BrandViewset

router = DefaultRouter()

router.register('categories', CategoryViewset, basename="categories")
router.register('produts', ProductViewset, basename="products")
router.register('brands', BrandViewset, basename="brands")

urlpatterns = [
    path('', include(router.urls)),
]