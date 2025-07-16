from django.urls import include, path
from rest_framework.routers import DefaultRouter

from adora.views import (
    BrandViewset,
    CarViewset,
    CashDiscountPercentViewset,
    CategoryViewset,
    CollaborateAndContactUsViewset,
    CommentViewSet,
    OrderViewSet,
    PostViewSet,
    ProductViewset,
)

router = DefaultRouter()

router.register("categories", CategoryViewset, basename="categories")
router.register("products", ProductViewset, basename="products")
router.register("brands", BrandViewset, basename="brands")
router.register("cars", CarViewset, basename="cars")
router.register("comments", CommentViewSet, basename="comments")
router.register("orders", OrderViewSet, basename="orders")
router.register("blog", PostViewSet, basename="blogs")
router.register(
    "collaborate_contact",
    CollaborateAndContactUsViewset,
    basename="collaborate_contact",
),
router.register(
    "cash_discount_percent",
    CashDiscountPercentViewset,
    basename="cash_discount_percent",
)


urlpatterns = [
    path("", include(router.urls)),
]
