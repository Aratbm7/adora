from django.urls import path, include
from rest_framework.routers import DefaultRouter
from adora.views import CategoryViewset, ProductViewset, BrandViewset, CommentViewSet

router = DefaultRouter()

router.register('categories', CategoryViewset, basename="categories")
router.register('products', ProductViewset, basename="products")
router.register('brands', BrandViewset, basename="brands")
router.register('comments', CommentViewSet, basename="comments")

urlpatterns = [
    path('', include(router.urls)),
]