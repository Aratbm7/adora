import json
import os
import time
import traceback

import requests
from django.db.models import Prefetch
from django_filters import rest_framework as filters
from drf_yasg.utils import swagger_auto_schema
from fuzzywuzzy import fuzz
from requests.exceptions import ConnectionError
from rest_framework.decorators import action

# from rest_framework.generics import ListAPIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from yaml import serialize

from adora.filters import ProductFilter
from adora.models import (
    Banner,
    Brand,
    Car,
    Category,
    Collaborate_Contact,
    Comment,
    Order,
    Post,
    Product,
)
from adora.paginations import ProductPagination
from adora.serializers import (
    BrandSerializer,
    CarSerializer,
    CategoryWhitChildrenSerializer,
    CollaborateAndContactUsSerializer,
    CommentSerializer,
    OrderListSerializer,
    OrderRejectedReasonSerializer,
    OrderSerializer,
    PostSerializer,
    ProductEmallsSerilizers,
    ProductListSerializer,
    ProductRetrieveSerializer,
    ProductSearchSerializer,
    ProductTorobSerilizers,
)
from adora.tasks import send_order_status_message
from core.permissions import (  # object_level_permissions,
    object_level_permissions_restricted_actions,
    personal_permissions,
)

# from drf_yasg import openapi
# from typing import Optional, Dict
from rest_framework import permissions, status, viewsets


class CategoryViewset(ModelViewSet):
    permission_classes = [personal_permissions({"u": 3, "a": 63, "o": 3})]
    http_method_names = ["header", "put", "post", "get"]
    children_prefetch = Prefetch("children", queryset=Category.objects.all())
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related(
        children_prefetch
    )
    serializer_class = CategoryWhitChildrenSerializer

    @action(
        detail=False,
        methods=["get"],
        url_name="banners",
        permission_classes=[permissions.AllowAny],
    )
    def banners(self, request: Request):
        where = request.query_params.get("where")
        if not where:
            return Response(
                {"message": 'Missing require parameter "where"'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        banners = Banner.objects.filter(where=where).values()
        return Response(banners, status=status.HTTP_200_OK)


class ProductViewset(ModelViewSet):
    queryset = (
        Product.objects.select_related(
            "category",
            "brand",
        )
        .prefetch_related(
            "compatible_cars",
            "similar_products",
            "images",
        )
        .all()
        .order_by("-count")
    )
    serializer_class = ProductRetrieveSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ProductFilter
    pagination_class = ProductPagination
    permission_classes = [personal_permissions({"u": 3, "a": 63, "o": 3})]

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
        responses={200: ProductRetrieveSerializer(many=True)},
    )
    def list(self, request: Request, *args, **kwargs):
        query_params = request.query_params
        min_price = query_params.get("min_price", "")
        max_price = query_params.get("max_price", "")

        self.serializer_class = ProductListSerializer
        if (min_price.isdigit() and int(min_price) < 0) or len(min_price) > 20:
            return Response(
                {
                    "error": "min_price query_param can not be nagative number or more than 20 digits"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (max_price.isdigit() and int(max_price) < 0) or len(max_price) > 20:
            return Response(
                {
                    "error": "max_price queryparam can not be nagative number or more than 20 digits"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().list(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["GET"],
        url_path="search",
        permission_classes=[permissions.AllowAny],
    )
    def search(self, request: Request, *args, **kwargs):
        query = request.query_params.get("query", "").strip()
        if query:
            products = (
                Product.objects.all()
                .select_related("category", "brand", "material")
                .prefetch_related("images", "compatible_cars")
            )

            similar_products = []
            for product in products:
                title = product.fa_name
                ratio = fuzz.WRatio(query, title)
                print("ratio", ratio)
                if ratio >= 50:
                    similar_products.append((product, ratio))

            similar_products.sort(key=lambda x: x[1], reverse=True)
            sorted_products = [product for product, ratio in similar_products]
            serializer = ProductSearchSerializer(sorted_products, many=True)

            return Response(serializer.data)

        else:
            return Response(
                {"detail": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(
        detail=False,
        methods=["Get"],
        url_path="torob",
        permission_classes=[permissions.AllowAny],
    )
    def products_torob(self, request: Request):
        products = Product.objects.all()
        # .select_related( 'category', 'brand', 'material' )\
        #     .prefetch_related('images','compatible_cars' )
        serialize = ProductTorobSerilizers(products, many=True)
        return Response(serialize.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["Get"],
        url_path="emalls",
        permission_classes=[permissions.AllowAny],
    )
    def products_emalls(self, request: Request):
        products = Product.objects.prefetch_related("images").all()
        # .select_related( 'category', 'brand', 'material' )\
        #     .prefetch_related('images','compatible_cars' )
        serialize = ProductEmallsSerilizers(products, many=True)
        return Response(
            {"pages_count": 1, "products": serialize.data}, status=status.HTTP_200_OK
        )


class BrandViewset(ModelViewSet):
    permission_classes = [personal_permissions({"u": 3, "a": 63, "o": 3})]
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


class CarViewset(ModelViewSet):
    http_method_names = ["get"]
    permission_classes = [personal_permissions({"u": 3, "a": 63, "o": 3})]
    queryset = Car.objects.all()
    serializer_class = CarSerializer


class CommentViewSet(ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [
        personal_permissions({"u": 31, "a": 63, "o": 3}),
        object_level_permissions_restricted_actions({"u": 31, "a": 63, "o": 3}),
    ]

    def get_queryset(self):
        if self.action == "list":
            return Comment.objects.filter(parent__isnull=True).select_related(
                "product", "user"
            )

        # if self.action == 'retrieve':
        #     return Comment.objects.all().select_related('product', 'user')

        return Comment.objects.all().select_related("product", "user")

    def perform_create(self, serializer):
        parent_id = self.request.data.get("parent")
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

    @action(detail=True, methods=["get"])
    def replies(self, request: Request, pk=None):
        comment = self.get_object()
        serializer = self.get_serializer(comment.get_replies(), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my-comments', permission_classes=[permissions.IsAuthenticated])
    def my_comments(self, request:Request):
        comments = Comment.objects.filter(user=request.user)
        serializer = self.get_serializer(comments, many=True)
        return Response(serializer.data)        
        
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [
        personal_permissions({"u": 31, "a": 63, "o": 3}),
        object_level_permissions_restricted_actions({"u": 31, "a": 63, "o": 3}),
    ]

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_queryset(self):
        if self.request.user.is_authenticated:
            if self.action == "list":
                user = self.request.user

                return Order.objects.filter(user=user)

            # if self.action == 'retrieve':
            #     return Comment.objects.all().select_related('product', 'user')

            return Order.objects.all()

        else:
            return Order.objects.none()

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return OrderListSerializer
        if self.action == "create":
            return OrderSerializer
        return super().get_serializer_class()

    def perform_update(self, serializer):
        # Ensure the user is automatically assigned from the request
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        # Check if the user has permission to delete this comment
        if instance.user != self.request.user:
            raise PermissionDenied("You do not have permission to delete this comment.")

    @action(
        detail=False,
        methods=["get"],
        url_path="payment-request-info",
        permission_classes=[permissions.IsAuthenticated],
    )
    def payment_status(self, request: Request):
        try:
            tracking_number = request.query_params.get("tracking_number")

            if not tracking_number:
                return Response(
                    {"message": "Tracking number is missing."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(tracking_number=tracking_number).first()

            if not order:
                return Response(
                    {
                        "message": f"There is no Order with this tracking number {tracking_number}."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            max_attempts = 5
            for attempt in range(max_attempts):
                if hasattr(order, "receipt"):
                    order_receipt = order.receipt
                    break  # Exit the loop if receipt exists
                else:
                    if attempt < max_attempts - 1:  # Avoid sleep after the last attempt
                        time.sleep(5)  # Wait for 5 seconds before retrying

            # Check if a receipt was found after the retries
            if not hasattr(order, "receipt"):
                return Response(
                    {
                        "message": "Order receipt not created after multiple attempts, please try again later!"
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            request_code = order.receipt.request_code
            if request_code == 100:
                return Response(
                    {
                        "payment_url": f"{os.environ.get('ZARIN_START_PAY_URL')}/{order_receipt.authority}",
                        "message": order_receipt.request_msg,
                        "fee": order_receipt.fee,
                        "amount": int(order.total_price),
                    },
                    status=status.HTTP_200_OK,
                )

            else:
                return Response(
                    {"message": order_receipt.error_msg, "code": request_code},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
        except Exception as e:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An unexpected error!!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(
        detail=False,
        methods=["get"],
        url_path="payment-verified",
        permission_classes=[permissions.IsAuthenticated],
    )
    def payment_verified(
        self,
        request: Request,
    ):
        # try:
        payment_status = request.query_params.get("payment_status", "")
        authority = request.query_params.get("authority", "")
        tracking_number = request.query_params.get("tracking_number")

        if not authority or not tracking_number or not payment_status:
            return Response(
                {
                    "message": "Missing required parameters: payment status or authority and/or tracking_number."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = Order.objects.filter(tracking_number=tracking_number).first()

        if not order:
            return Response(
                {"message": f"No order found with tracking number {tracking_number}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        order_receipt = order.receipt

        if not order_receipt:
            return Response(
                {"message": "No order receipt found for this order."},
                status=status.HTTP_404_NOT_FOUND,
            )

        order_authority = order_receipt.authority

        if order_authority != authority:
            return Response(
                {"message": f"Invalid authority {authority} for this order."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_full_name = (
            f"{order.user.profile.first_name} {order.user.profile.last_name}"
        )

        if payment_status == "OK":

            try:
                zarin_verify_url = os.environ.get("ZARIN_VERIFY_URL")
                verify_res = requests.post(
                    zarin_verify_url,
                    headers={
                        "accept": "application/json",
                        "content-type": "application/json",
                    },
                    data=json.dumps(
                        {
                            "merchant_id": os.environ.get("ZARIN_MERCHANT_ID"),
                            "amount": int(order.total_price),
                            # "amount":1200,
                            "authority": order_authority,
                        }
                    ),
                )

                verify_res_json = verify_res.json()
            except ConnectionError:
                return Response(
                    {"message": "Connection error Try again"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            except Exception:
                return Response(
                    {"message": "Server side error Try again"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            if verify_res.status_code == 200:
                verfiy_data = verify_res_json.get("data", {})
                order_success_text_code = os.environ.get("ORDER_SUCCESS")

                sms_message = [user_full_name, order.tracking_number]

                card_hash = verfiy_data.get("card_hash")
                card_pan = verfiy_data.get("card_pan")
                ref_id = verfiy_data.get("ref_id")
                fee_type = verfiy_data.get("fee_type")
                code = verfiy_data.get("code")
                message = verfiy_data.get("message")

                order_receipt.card_hash = verfiy_data.get("card_hash")
                order_receipt.ref_id = verfiy_data.get("ref_id")
                order_receipt.fee_type = verfiy_data.get("fee_type")
                order_receipt.card_pan = verfiy_data.get("card_pan")
                order_receipt.verify_code = verfiy_data.get("code")
                order_receipt.save()

                # Update user wallet_balance
                if order.use_wallet_balance:
                    order.user.profile.wallet_balance = order.order_reward
                    order.user.profile.save()

                else:
                    order.user.profile.wallet_balance += order.order_reward
                    order.user.profile.save()

                order.payment_status = "C"
                order.save()
                send_order_status_message.delay(
                    str(order.user.phone_number).replace("+98", "0"),
                    sms_message,
                    int(order_success_text_code),
                )

                return Response(
                    {
                        "message": message,
                        "code": code,
                        "fee_type": fee_type,
                        "ref_id": ref_id,
                        "card_pan": card_pan,
                        "card_hash": card_hash,
                    },
                    status=status.HTTP_200_OK,
                )

            else:
                verify_data = verify_res_json.get("errors", {})
                order_failed_text_code = os.environ.get("ORDER_FAILED")
                message_sms = [user_full_name]
                verify_code = verify_data.get("code")
                message = verify_data.get("message")
                order_receipt.verify_code = verify_code
                order_receipt.error_msg = message
                order_receipt.save()
                order.payment_status = "F"
                order.save()
                send_order_status_message.delay(
                    str(order.user.phone_number).replace("+98", "0"),
                    message_sms,
                    int(order_failed_text_code),
                )

            return Response(
                {"message": message, "code": verify_code}, status=verify_res.status_code
            )

        elif payment_status == "NOK":
            order_failed_text_code = os.environ.get("ORDER_FAILED")
            message_sms = [user_full_name]

            order_receipt.error_msg = "NOK"
            order_receipt.save()
            order.payment_status = "F"
            order.save()
            send_order_status_message.delay(
                str(order.user.phone_number).replace("+98", "0"),
                message_sms,
                int(order_failed_text_code),
            )

            return Response(
                {"message": "Payment failed and order status updated to Failed."},
                status=status.HTTP_200_OK,
            )

        else:
            return Response(
                {
                    "message": 'Invalid value for payment_status parameter. Must be "OK" or "NOK".'
                },
                status=status.HTTP_200_OK,
            )

    def _get_full_name_or_phone_number(self, order: Order) -> str:
        user_prfile = order.user.profile
        name = user_prfile.first_name
        last_name = user_prfile.last_name
        full_name = f"{user_prfile.first_name} {user_prfile.last_name}"
        if name or last_name:
            return full_name

        return str(order.user.phone_number).replace("+98", "0")

    @action(
        detail=False,
        methods=["post"],
        url_path="rejected_ask",
        permission_classes=[permissions.AllowAny],
        serializer_class=OrderRejectedReasonSerializer,
    )
    def rejected_ask(self, request):

        try:
            tracking_number = request.query_params.get("tracking_number")

            serializer = OrderRejectedReasonSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            returned_asked_reason = serializer.validated_data["returned_rejected_reason"]
            if not tracking_number:
                return Response(
                    {"message": "Tracking number is missing."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(tracking_number=tracking_number).first()

            if not order:
                return Response(
                    {
                        "message": f"There is no Order with this tracking number {tracking_number}."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Prevent to send more than one Returned ask
            if not order.returned_status == "N":
                return Response(
                    {"message": "Any order can asked for request just once"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            full_name = self._get_full_name_or_phone_number(order)
            phone_number = str(order.user.phone_number).replace("+98", "0")
            text_code = os.environ.get("ORDER_RETURNED_ASK")
            print(text_code)
            send_order_status_message.delay(
                phone_number, [full_name, tracking_number], int(text_code)
            )
            order.returned_asked_reason = returned_asked_reason
            order.returned_status = "RA"
            order.save()

            return Response(
                {"message": "Rjected ask was successfully"}, status=status.HTTP_200_OK
            )

        except Exception as e:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An unexpected error!!"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PostViewSet(ModelViewSet):
    http_method_names = ["get"]
    queryset = Post.objects.all()
    serializer_class = PostSerializer

    permission_classes = [permissions.AllowAny]

    
class CollaborateAndContactUsViewset(ModelViewSet):
    http_method_names = ["get", "post", "put"]
    queryset = Collaborate_Contact.objects.all()
    serializer_class = CollaborateAndContactUsSerializer
