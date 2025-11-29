import json
import os
import time
import traceback

import requests
from django.db.models import Prefetch
from django_filters import rest_framework as filters
from drf_yasg import openapi
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

# For snappay
from django.views import View
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from adora.filters import ProductFilter
from adora.models import (
    Banner,
    Brand,
    Car,
    CashDiscountPercent,
    Category,
    Collaborate_Contact,
    Comment,
    Order,
    OrderItem,
    OrderReceipt,
    Post,
    Product,
)
from adora.paginations import ProductPagination
from adora.serializers import (
    BrandSerializer,
    CarSerializer,
    CashDiscountPercentSerializer,
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
    SnapOrderUpdateSerilizer,
)
from adora.tasks import (
    get_torobpay_access_token,
    get_snap_pay_access_token,
    send_order_status_message,
    azkivam_verify,
)
from core.permissions import (  # object_level_permissions,
    object_level_permissions_restricted_actions,
    personal_permissions,
)

# from drf_yasg import openapi
from typing import Any, Dict, Optional, cast
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
        category_id = query_params.get("category", "")
        hierarchy = []

        if category_id.isdigit():
            try:
                category = Category.objects.get(id=int(category_id))
                hierarchy = category.get_hierarchy()

            except Category.DoesNotExist:
                pass

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

        return Response(
            {
                "category_hierarchy": hierarchy,
                "results": super().list(request, *args, **kwargs).data,
            },
            status=status.HTTP_200_OK,
        )

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

    @action(
        detail=False,
        methods=["get"],
        url_path="my-comments",
        permission_classes=[permissions.IsAuthenticated],
    )
    def my_comments(self, request: Request):
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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        try:
            print("Starting serializer.save")
            instance = serializer.save(user=self.request.user)
            print(f"Order created with ID: {instance.id}")

        except ValidationError as e:
            print(f"ValidationError: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Exception: {str(e)}")
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
        url_path="zarinpal-payment-request-info",
        permission_classes=[permissions.IsAuthenticated],
    )
    def zarinpal_payment_status(self, request: Request):
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
        except Exception:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An unexpected error!!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _get_full_name_or_phone_number(self, order: Order) -> str:
        user_prfile = order.user.profile
        name = user_prfile.first_name or ""
        last_name = user_prfile.last_name or ""
        full_name = f"{name} {last_name}"
        if full_name.strip():
            return full_name.strip()

        # return str(order.user.phone_number).replace("+98", "0")
        return "کاربر آدورا یدک"

        # user_prfile = order.user.profile
        # name = user_prfile.first_name
        # last_name = user_prfile.last_name
        # full_name = f"{user_prfile.first_name} {user_prfile.last_name}"
        # if name or last_name:
        #     return full_name

        # return str(order.user.phone_number).replace("+98", "0")

    def _success_sms(self, order: Order):
        send_order_status_message.delay(
            str(order.user.phone_number).replace("+98", "0"),
            [self._get_full_name_or_phone_number(order), order.tracking_number],
            int(os.getenv("ORDER_SUCCESS", 0)),
        )

    def _failed_sms(self, order: Order):
        send_order_status_message.delay(
            str(order.user.phone_number).replace("+98", "0"),
            [self._get_full_name_or_phone_number(order)],
            int(os.getenv("ORDER_FAILED", 0)),
        )

    @action(
        detail=False,
        methods=["get"],
        # url_path="zarinpal-payment-verification",
        url_path="zarinpal-payment-verified",
        permission_classes=[permissions.IsAuthenticated],
    )
    def zarinpal_payment_verified(self, request: Request):
        order_receipt = None

        payment_status = request.query_params.get("payment_status", "")
        authority = request.query_params.get("authority", "")
        tracking_number = request.query_params.get("tracking_number")

        if not authority or not tracking_number or not payment_status:
            return Response(
                {
                    "message": "Missing required parameters: payment_status, authority, or tracking_number."
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

        if order_receipt.authority != authority:
            return Response(
                {
                    "message": f"Invalid authority: {authority} does not match this order."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment_status == "OK":
            try:
                zarin_verify_url = os.getenv("ZARIN_VERIFY_URL", "")
                verify_payload = {
                    "merchant_id": os.getenv("ZARIN_MERCHANT_ID"),
                    "amount": int(order.total_price),
                    "authority": authority,
                }

                verify_response = requests.post(
                    zarin_verify_url,
                    headers={
                        "accept": "application/json",
                        "content-type": "application/json",
                    },
                    data=json.dumps(verify_payload),
                )

                if verify_response.status_code != 200:
                    return Response(
                        {
                            "message": "Zarinpal server returned error",
                            "status": verify_response.status_code,
                        },
                        status=status.HTTP_502_BAD_GATEWAY,
                    )

                verify_json = verify_response.json()

            except requests.exceptions.RequestException as e:
                return Response(
                    {"message": f"Connection error: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            except Exception as e:
                return Response(
                    {"message": f"Unexpected server error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            if "data" in verify_json:
                data = verify_json["data"]
                order_receipt.card_hash = data.get("card_hash")
                order_receipt.card_pan = data.get("card_pan")
                order_receipt.ref_id = data.get("ref_id")
                order_receipt.fee_type = data.get("fee_type")
                order_receipt.verify_code = data.get("code")
                order_receipt.save()

                # واریز پاداش به کیف پول کاربر
                profile = order.user.profile
                if order.use_wallet_balance:
                    profile.wallet_balance = order.order_reward
                else:
                    profile.wallet_balance += order.order_reward
                profile.save()

                order.payment_status = "C"
                order.save()
                self._success_sms(order)

                return Response(
                    {
                        "message": data.get("message"),
                        "code": data.get("code"),
                        "fee_type": data.get("fee_type"),
                        "ref_id": data.get("ref_id"),
                        "card_pan": data.get("card_pan"),
                        "card_hash": data.get("card_hash"),
                    },
                    status=status.HTTP_200_OK,
                )

            elif "errors" in verify_json:
                errors = verify_json["errors"]
                order_receipt.verify_code = errors.get("code")
                order_receipt.error_msg = errors.get("message")
                order_receipt.save()

                order.payment_status = "F"
                order.save()
                self._failed_sms(order)

                return Response(
                    {
                        "message": errors.get("message", "Verification failed"),
                        "code": errors.get("code", "N/A"),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            else:
                return Response(
                    {
                        "message": "Unexpected response from Zarinpal.",
                        "response": verify_json,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        elif payment_status == "NOK":
            order_receipt.error_msg = "Payment canceled by user."
            order_receipt.save()
            order.payment_status = "F"
            order.save()
            self._failed_sms(order)

            return Response(
                {"message": "Payment failed and order status updated to Failed."},
                status=status.HTTP_200_OK,
            )

        else:
            return Response(
                {"message": "Invalid value for payment_status. Must be 'OK' or 'NOK'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "access_token",
                openapi.IN_QUERY,
                description="The Torob Pay access token.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "tracking_number",
                openapi.IN_QUERY,
                description="Order tracking number.",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={200: "OK", 400: "Bad Request"},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="torobpay-payment-verification",
        permission_classes=[permissions.IsAuthenticated],
    )
    def torobpay_payment_verify(self, request: Request):
        order_receipt = None  # برای جلوگیری از ارور در except
        try:
            TOROBPAY_BASE_URL = os.getenv("TOROBPAY_BASE_URL")
            TOROBPAY_PAYMENT_VERIFY = os.getenv("TOROBPAY_PAYMENT_VERIFY")
            TOROBPAY_PAYMENT_SETTLE = os.getenv("TOROBPAY_PAYMENT_SETTLE")

            # access_token = request.query_params.get("torob_access_token", "")
            access_token = get_torobpay_access_token()
            tracking_number = request.query_params.get("tracking_number", "")

            if not tracking_number or not access_token:
                return Response(
                    {
                        "message": "Missing required parameters: tracking_number or torob_access_token"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(tracking_number=tracking_number).first()
            if not order:
                return Response(
                    {
                        "message": f"No order found with tracking number {tracking_number}."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not order.torob_payment_token:
                return Response(
                    {"message": "No order payment token found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            order_receipt: OrderReceipt = order.receipt
            if not order_receipt:
                return Response(
                    {"message": "No order receipt found for this order."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            header = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }

            # Step 1: Verify payment
            verify_response = requests.post(
                url=f"{TOROBPAY_BASE_URL}/{TOROBPAY_PAYMENT_VERIFY}",
                headers=header,
                data=json.dumps({"paymentToken": order.torob_payment_token}),
            )
            verify_data = verify_response.json()

            if verify_data.get("successful"):
                print("Payment verification successful")
                transaction_id = verify_data.get("response", {}).get(
                    "transactionId", ""
                )
                order.payment_status = "TV"
                order.save()

                order_receipt.azkivam_error_message = verify_data
                order_receipt.torob_transaction_id = transaction_id
                order_receipt.save()

                # Step 2: Settle payment
                settle_response = requests.post(
                    url=f"{TOROBPAY_BASE_URL}/{TOROBPAY_PAYMENT_SETTLE}",
                    headers=header,
                    data=json.dumps({"paymentToken": order.torob_payment_token}),
                )
                settle_data = settle_response.json()

                if settle_data.get("successful"):
                    order_receipt.azkivam_error_message = settle_data
                    order_receipt.torob_transaction_id = settle_data.get(
                        "response", {}
                    ).get("transactionId", "")
                    order.save()
                    order.payment_status = "C"
                    order.save()
                    self._success_sms(order)
                    return Response(
                        {
                            "message": "Successfully verified and settled payment.",
                            "response": settle_data.get("response", {}),
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    error_message = settle_data.get("errorData", {}).get(
                        "message", "Unknown error"
                    )
                    error_code = settle_data.get("errorData", {}).get(
                        "errorCode", "Unknown code"
                    )
                    order_receipt.azkivam_error_message += error_message
                    order_receipt.torob_error_code = error_code
                    order_receipt.save()
                    order.payment_status = "TV"
                    order.save()
                    self._failed_sms(order)
                    return Response(
                        {
                            "message": "Payment settlement failed.",
                            "TorobPayError": settle_data.get("errorData", {}),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            else:
                error_message = verify_data.get("errorData", {}).get(
                    "message", "Unknown error"
                )
                error_code = verify_data.get("errorData", {}).get(
                    "errorCode", "Unknown code"
                )
                order_receipt.azkivam_error_message = error_message
                order_receipt.torob_error_code = error_code
                order_receipt.save()
                order.payment_status = "F"
                order.save()
                self._failed_sms(order)
                return Response(
                    {
                        "message": "Payment verification failed.",
                        "TorobPayError": verify_data.get("errorData", {}),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except requests.exceptions.RequestException as e:
            error_message = f"Connection error: {str(e)}"
            print(error_message)
            if order_receipt:
                order_receipt.torob_error_message = error_message
                order_receipt.save()
            return Response(
                {"message": error_message}, status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            error_message = traceback.format_exc()
            print(error_message)
            if order_receipt:
                order_receipt.torob_error_message = error_message
                order_receipt.save()
            return Response(
                {"message": "An unexpected error occurred.", "trace": error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # TODO : Change permission to IsAuthenticated
    @action(
        detail=False,
        methods=["get"],
        url_path="torobpay-access-token",
        permission_classes=[permissions.IsAuthenticated],
        # permission_classes=[permissions.AllowAny],
    )
    def get_torob_access_token(sefl, request):

        access_token = get_torobpay_access_token()
        if not access_token:
            return Response(
                {"message": "Can't get access token try again"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"access_token": access_token}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "access_token",
                openapi.IN_QUERY,
                description="The Torob Pay access token.",
                type=openapi.TYPE_STRING,
                # default="ALFDJKNALDSJKAJSD;IFJAISFUAJLKFJAOSDF.ASDFHALDFAS=="
            ),
            openapi.Parameter(
                "amount",
                openapi.IN_QUERY,
                description="Amount of order price in Rial",
                type=openapi.TYPE_STRING,
                # default="ADO_ALASDKFJALDLA"
            ),
        ],
        responses={200: "OK", 400: "Bad Request"},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="torob-check-merchant-eligible",
        permission_classes=[permissions.IsAuthenticated],
    )
    def torob_merchant_eligible(self, request):
        try:
            TOROBPAY_BASE_URL = os.getenv("TOROBPAY_BASE_URL")
            TOROBPAY_PAYMENT_ELIGIBLE = os.getenv("TOROBPAY_PAYMENT_ELIGIBLE")
            access_token = get_torobpay_access_token()

            amount = request.query_params.get("amount", "")
            print("access_token", access_token)
            print("amount", amount)

            if not amount or not access_token:
                return Response(
                    {
                        "message": "Missing required parameters {amount} or {torob_access_token}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            header = {
                "Authorization": f"Bearer {access_token}",
                "content-type": "application/json",
            }

            res = requests.get(
                url=f"{TOROBPAY_BASE_URL}/{TOROBPAY_PAYMENT_ELIGIBLE}?amount={amount}",
                headers=header,
            ).json()

            if res.get("successful", False):
                return Response(res.get("response"), status=status.HTTP_200_OK)
            else:
                return Response(
                    res.get("errorData"), status=status.HTTP_400_BAD_REQUEST
                )

        except ConnectionError:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An Cennection error!! Try again please"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An unexpected error!!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(
        detail=False,
        methods=["post"],
        url_path="snap-update",
        permission_classes=[permissions.IsAuthenticated],
    )
    def snap_update(self, request: Request):
        try:
            serializer = SnapOrderUpdateSerilizer(data=request.data)

            print("It come from snappay-update",request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            tracking_number = data.get("tracking_number")
            items = data.get("items")
            print("From snap-update",data)

            # پیدا کردن سفارش
            try:
                order = Order.objects.get(tracking_number=tracking_number)
            except Order.DoesNotExist:
                return Response(
                    {"error": "Order not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # چک کردن وجود payment token
            if not order.snap_payment_token:
                return Response(
                    {"error": "Order does not have a snap payment token"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # محاسبه مبلغ جدید و ساخت لیست آیتم‌های نهایی
            total_amount = 0
            final_items = []

            for item in items:
                try:
                    product = Product.objects.get(id=item["id"])
                except Product.DoesNotExist:
                    return Response(
                        {"error": f"Product with id {item['id']} not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                count = item["count"]
                product_price = product.get_discounted_price()
                total_amount += product_price * count
                final_items.append((product, count, product_price))

            # چک کردن که مبلغ جدید از مبلغ قبلی بیشتر نباشد
            old_total = order.total_price
            if total_amount > old_total:
                return Response({
                    "error": "SnappPay does not allow price increase",
                    "old_amount": float(old_total),
                    "new_amount": float(total_amount)
                }, status=status.HTTP_400_BAD_REQUEST)

            # ساخت لیست آیتم‌ها برای payload
            cart_items_list = list(map(
                lambda item: {
                    "id": item[0].id,
                    "amount": int(item[2] * 10),  # تبدیل به ریال
                    "category": "ابزار و یدک خودرو",
                    "count": item[1],
                    "name": item[0].fa_name,
                    "commissionType": 10801
                },
                final_items
            ))


            total_amount += order.delivery_cost
            print(order.user.profile.wallet_balance, "profile wallet balance from snap update")
            print(order.amount_used_wallet_balance, "used wallet balance from snap update")
            print(total_amount, "total amount from snap update")
            # محاسبه مبلغ با در نظر گرفتن کیف پول برای مبلغ جدید
            if order.use_wallet_balance:
                wallet_balance = order.amount_used_wallet_balance
                if wallet_balance >= total_amount:
                    print(wallet_balance, "total amount from snap update")
                    print(total_amount, "total amount from snap update")
                    # کل مبلغ از کیف پول پرداخت می‌شود
                    print("Wallet_balance is greater than total_amout")
                    amount_to_pay = 0
                    wallet_discount = int(total_amount * 10)
                else:

                    # بخشی از کیف پول استفاده می‌شود
                    amount_to_pay = int((total_amount - wallet_balance) * 10)
                    wallet_discount = int(wallet_balance * 10)
            else:
                # کیف پول استفاده نمی‌شود
                amount_to_pay = int(total_amount * 10)
                wallet_discount = 0

            # ساخت payload برای درخواست update

            print(amount_to_pay, "from snap_update")
            payload_data = {
                "amount": amount_to_pay,  # مبلغی که باید پرداخت شود
                "cartList": [
                    {
                        "cartId": order.id,
                        "cartItems": cart_items_list,
                        "isShipmentIncluded": True if order.delivery_cost else False,
                        "isTaxIncluded": True,
                        "shippingAmount": int(order.delivery_cost * 10) if order.delivery_cost else 0,
                        "taxAmount": 0,
                        "totalAmount": int(total_amount * 10)
                    }
                ],
                "discountAmount": 0,
                "externalSourceAmount": wallet_discount,
                "paymentMethodTypeDto": "INSTALLMENT",
                "paymentToken": order.snap_payment_token
            }

            print("from snap update: ",payload_data)
            # ارسال درخواست به اسنپ پی
            SNAP_PAY_BASE_URL = os.getenv("SNAP_PAY_BASE_URL")
            SNAP_PAY_UPDATE_ENDPOINT = os.getenv("SNAP_PAY_UPDATE_ENDPOINT")

            access_token = get_snap_pay_access_token()

            header = {
                "content-type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }

            url = f"{SNAP_PAY_BASE_URL}{SNAP_PAY_UPDATE_ENDPOINT}"

            response = requests.post(
                url=url,
                headers=header,
                data=json.dumps(payload_data),
            )

            response_dict = response.json()

            if response_dict.get("successful", False):
                # اگر موفقیت‌آمیز بود، آیتم‌های قبلی را حذف و آیتم‌های جدید را اضافه کن
                order.order_items.all().delete()

                for product, count, price in final_items:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=count,
                        sold_price=price
                    )

                # به‌روزرسانی مبلغ کل سفارش
                order.total_price = int(amount_to_pay / 10)
                order.payment_status = "SU"
                order.save()

                return Response({
                    "message": "Order updated successfully",
                    "transactionId": response_dict.get("response", {}).get("transactionId"),
                    "old_total": float(old_total),
                    "new_total": float(amount_to_pay / 10)
                }, status=status.HTTP_200_OK)
            else:
                error_data = response_dict.get("errorData", {})
                error_message = f"{error_data.get('errorCode', '')} - {error_data.get('message', '')}"
                print(error_message)

                return Response({
                    "error": "Failed to update order in SnappPay",
                    "details": error_message,
                    "response": response_dict
                }, status=status.HTTP_400_BAD_REQUEST)

        except ConnectionError as e:
            print("Connection Error")
            return Response({
                "error": "Connection error to SnappPay",
                "details": str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as e:
            print(f"Error in snap_update: {traceback.format_exc()}")
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(
        detail=False,
        methods=["get"],
        url_path="snap-check-merchant-eligible",
        permission_classes=[permissions.IsAuthenticated],
    )
    def snap_merchant_eligible(self, request):
        try:
            SNAP_PAY_BASE_URL = os.getenv("SNAP_PAY_BASE_URL")
            SNAP_PAY_ELIGIBLE_ENDPOINT = os.getenv("SNAP_PAY_ELIGIBLE_ENDPOINT")
            access_token = get_snap_pay_access_token()
            print(SNAP_PAY_BASE_URL)
            print(SNAP_PAY_ELIGIBLE_ENDPOINT)
            amount = request.query_params.get("amount", "")
            print("access_token", access_token)
            print("amount", amount)

            if not amount or not access_token:
                return Response(
                    {
                        "message": "Missing required parameters {amount} or {snap_access_token}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            header = {
                "Authorization": f"Bearer {access_token}",
                "content-type": "application/json",
            }

            res = requests.get(
                url=f"{SNAP_PAY_BASE_URL}{SNAP_PAY_ELIGIBLE_ENDPOINT}?amount={amount}",
                headers=header,
            ).json()

            if res.get("successful", False):
                return Response(res.get("response"), status=status.HTTP_200_OK)
            else:
                return Response(
                    res.get("errorData"), status=status.HTTP_400_BAD_REQUEST
                )

        except ConnectionError:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An Cennection error!! Try again please"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An unexpected error!!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(
        detail=False,
        methods=["get"],
        url_path="rejected_ask",
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=OrderRejectedReasonSerializer,
    )
    def rejected_ask(self, request):

        try:
            tracking_number = request.query_params.get("tracking_number")

            serializer = OrderRejectedReasonSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = cast(Dict[str, Any], serialize.validated_data)
            returned_asked_reason = cast(Dict[str, Any], validated_data)
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

            self._failed_sms(order)
            # Prevent to send more than one Returned ask
            if not order.returned_status == "N":
                return Response(
                    {"message": "Any order can asked for request just once"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            full_name = self._get_full_name_or_phone_number(order)
            phone_number = str(order.user.phone_number).replace("+98", "0")
            text_code = os.environ.get("ORDER_RETURNED_ASK", 0)
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

    @action(
        detail=False,
        methods=["get"],
        url_path="azkivam-payment-verification",
        permission_classes=[permissions.IsAuthenticated],
    )
    def azkivam_payment_verification(self, request: Request):
        try:
            tracking_number = request.query_params.get("tracking_number")
            if not tracking_number:
                return Response(
                    {"message": "Missing required parameters: tracking_number!!"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(tracking_number=tracking_number).first()
            if not order:
                return Response(
                    {
                        "message": f"No order found with tracking number {tracking_number}."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not order.azkivam_payment_token:
                return Response(
                    {"message": "No order payment token found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            order_receipt: OrderReceipt = order.receipt
            if not order_receipt:
                return Response(
                    {"message": "No order receipt found for this order."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            res = azkivam_verify(order)

            if res is None:
                return Response(
                    {
                        "message": "Some error occured please see order receipt",
                        "trace": str(traceback.format_exc()),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if res.status_code == 200:
                self._success_sms(order)
            else:
                self._failed_sms(order)

            return Response(
                {"message": "Response is taken from azki see data", "data": res.json()}
            )

        except requests.exceptions.RequestException as e:
            error_message = f"Connection error: {str(e)}"
            print(error_message)
            if order_receipt:
                order_receipt.azkivam_error_message = error_message
                order_receipt.save()
            return Response(
                {"message": error_message}, status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            error_message = traceback.format_exc()
            print(error_message)
            if order_receipt:
                order_receipt.azkivam_error_message = error_message
                order_receipt.save()
            return Response(
                {"message": "An unexpected error occurred.", "trace": error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False,
        methods=["get"],
        url_path="azkivam-payment-failed",
        permission_classes=[permissions.IsAuthenticated],
    )
    def azkivam_payment_failed(self, request: Response):
        try:
            tracking_number = request.query_params.get("tracking_number")
            if not tracking_number:
                return Response(
                    {"message": "Missing required parameters: tracking_number!!"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(tracking_number=tracking_number).first()
            if not order:
                return Response(
                    {
                        "message": f"No order found with tracking number {tracking_number}."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not order.azkivam_payment_token:
                return Response(
                    {"message": "No order payment token found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            order_receipt: OrderReceipt = order.receipt
            if not order_receipt:
                return Response(
                    {"message": "No order receipt found for this order."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            order_receipt.azkivam_error_message = "پرداخت ناموفق"
            order_receipt.save()
            order.payment_status = "F"
            order.save()

            self._failed_sms(order)
            return Response({"message": "order status failed changed"})

        except Exception:
            error_message = traceback.format_exc()
            print(error_message)
            if order_receipt:
                order_receipt.azkivam_error_message = error_message
                order_receipt.save()
            return Response(
                {"message": "An unexpected error occurred.", "trace": error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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


class CashDiscountPercentViewset(ModelViewSet):
    http_method_names = [
        "get",
    ]
    queryset = CashDiscountPercent.objects.all()
    serializer_class = CashDiscountPercentSerializer


@method_decorator(csrf_exempt, name="dispatch")
class SnapPayCallbackView(View):
    """
    Handles SnapPay callback (POST or GET).
    - Receives transactionId and state
    - Calls verify and settle APIs
    - Redirects user to frontend page accordingly
    """

    def _get_full_name_or_phone_number(self, order: Order) -> str:
        user_prfile = order.user.profile
        name = user_prfile.first_name or ""
        last_name = user_prfile.last_name or ""
        full_name = f"{name} {last_name}"
        if full_name.strip():
            return full_name.strip()

        # return str(order.user.phone_number).replace("+98", "0")
        return "کاربر آدورا یدک"

        # user_prfile = order.user.profile
        # name = user_prfile.first_name
        # last_name = user_prfile.last_name
        # full_name = f"{user_prfile.first_name} {user_prfile.last_name}"
        # if name or last_name:
        #     return full_name

        # return str(order.user.phone_number).replace("+98", "0")

    def _success_sms(self, order: Order):
        send_order_status_message.delay(
            str(order.user.phone_number).replace("+98", "0"),
            [self._get_full_name_or_phone_number(order), order.tracking_number],
            int(os.getenv("ORDER_SUCCESS", 0)),
        )

    def _failed_sms(self, order: Order):
        send_order_status_message.delay(
            str(order.user.phone_number).replace("+98", "0"),
            [self._get_full_name_or_phone_number(order)],
            int(os.getenv("ORDER_FAILED", 0)),
        )

    def get(self, request):
        """Handle GET request from SnapPay"""
        FRONT_END_RETURN_URL = os.getenv("SNAP_PAY_RETURN_TO_THIS_URL")

        # نمایش تمام query parameters
        print("=" * 50)
        print("GET request received from SnapPay")
        print(f"Full URL: {request.build_absolute_uri()}")
        print(f"Query Parameters: {dict(request.GET)}")
        print(f"All GET params: {request.GET}")

        # نمایش تک تک پارامترها
        for key, value in request.GET.items():
            print(f"  {key}: {value}")

        # پارامترهای خاصی که احتمالاً اسنپ پی میفرسته
        transaction_id = request.GET.get("transactionId", "NOT_FOUND")
        state = request.GET.get("state", "NOT_FOUND")

        print(f"transactionId: {transaction_id}")
        print(f"state: {state}")
        print("=" * 50)

        return HttpResponseRedirect(f"{FRONT_END_RETURN_URL}?state=OK")

    def post(self, request):
        """Handle POST request from SnapPay"""

        print("POST REQUEST Received")
        order_receipt = None
        failed_stage = None

        try:
            SNAPPAY_BASE_URL = os.getenv("SNAP_PAY_BASE_URL")
            SNAPPAY_PAYMENT_VERIFY = os.getenv("SNAP_PAY_VERIFY_ENDPOINT")
            SNAPPAY_PAYMENT_SETTLE = os.getenv("SNAP_PAY_SETTLE_ENDPOINT")
            FRONT_END_RETURN_URL = os.getenv("SNAP_PAY_RETURN_TO_THIS_URL")
            print("CONTENT_TYPE", request.content_type)

            # دریافت داده‌ها از request
            if request.content_type == "application/json":
                data = json.loads(request.body)
            else:
                data = request.POST.dict()

            access_token = get_snap_pay_access_token()

            tracking_number = data.get("transactionId", "")
            state = data.get("state", "")

            print(f"Received - transactionId: {tracking_number}, state: {state}")

            # بررسی پارامترهای الزامی
            if not tracking_number or not access_token or not state:
                failed_stage = "out_error"
                return HttpResponseRedirect(
                    f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
                )

            # پیدا کردن سفارش
            order = Order.objects.filter(tracking_number=tracking_number).first()
            if not order:
                failed_stage = "internal_error"
                return HttpResponseRedirect(
                    f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
                )

            # پیدا کردن رسید سفارش
            order_receipt: Optional[OrderReceipt] = getattr(order, "receipt", None)
            if not order_receipt:
                failed_stage = "internal_error"
                return HttpResponseRedirect(
                    f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
                )

            # بررسی state از اسنپ‌پی
            if state == "FAILED":
                order_receipt.snap_error_message = "FAILED query parameter from Snap"
                order_receipt.save()
                order.payment_status = "F"
                order.save()
                self._failed_sms(order)
                failed_stage = "out_error"
                return HttpResponseRedirect(
                    f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
                )

            # بررسی توکن پرداخت
            if not order.snap_payment_token:
                failed_stage = "out_error"
                return HttpResponseRedirect(
                    f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
                )

            # تنظیم header برای درخواست‌ها
            header = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }

            # مرحله 1: تایید پرداخت (Verify)
            print("Calling verify API...")
            verify_response = requests.post(
                url=f"{SNAPPAY_BASE_URL}/{SNAPPAY_PAYMENT_VERIFY}",
                headers=header,
                data=json.dumps({"paymentToken": order.snap_payment_token}),
            )
            verify_data = verify_response.json()
            print(f"Verify response: {verify_data}")

            if verify_data.get("successful"):
                print("Payment verification successful")
                transaction_id = verify_data.get("response", {}).get(
                    "transactionId", ""
                )
                order.payment_status = "SV"
                order.save()

                order_receipt.azkivam_error_message = verify_data
                order_receipt.torob_transaction_id = transaction_id
                order_receipt.save()

                # مرحله 2: تسویه پرداخت (Settle)
                print("Calling settle API...")
                settle_response = requests.post(
                    url=f"{SNAPPAY_BASE_URL}/{SNAPPAY_PAYMENT_SETTLE}",
                    headers=header,
                    data=json.dumps({"paymentToken": order.snap_payment_token}),
                )
                settle_data = settle_response.json()
                print(f"Settle response: {settle_data}")

                if settle_data.get("successful"):
                    order_receipt.snap_error_message = settle_data
                    order_receipt.snap_transaction_id = settle_data.get(
                        "response", {}
                    ).get("transactionId", "")
                    order_receipt.save()
                    order.payment_status = "C"
                    order.save()
                    self._success_sms(order)
                    print("Payment completed successfully!")
                    return HttpResponseRedirect(f"{FRONT_END_RETURN_URL}?state=OK")
                else:
                    # خطا در تسویه
                    error_message = settle_data.get("errorData", {}).get(
                        "message", "Unknown error"
                    )
                    error_code = settle_data.get("errorData", {}).get(
                        "errorCode", "Unknown code"
                    )
                    order_receipt.snap_error_message = (
                        order_receipt.snap_error_message or ""
                    ) + error_message
                    order_receipt.snap_error_code = error_code
                    order_receipt.save()
                    order.payment_status = "SV"
                    order.save()
                    self._failed_sms(order)
                    failed_stage = "settle_error"
                    return HttpResponseRedirect(
                        f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
                    )
            else:
                # خطا در تایید پرداخت
                error_message = verify_data.get("errorData", {}).get(
                    "message", "Unknown error"
                )
                error_code = verify_data.get("errorData", {}).get(
                    "errorCode", "Unknown code"
                )
                order_receipt.snap_error_message = error_message
                order_receipt.snap_error_code = error_code
                order_receipt.save()
                order.payment_status = "F"
                order.save()
                self._failed_sms(order)
                failed_stage = "verify_error"
                return HttpResponseRedirect(
                    f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
                )

        except requests.exceptions.RequestException as e:
            error_message = f"Connection error: {str(e)}"
            print(error_message)
            if order_receipt:
                order_receipt.azkivam_error_message = error_message
                order_receipt.save()
            failed_stage = "connection_error"
            FRONT_END_RETURN_URL = os.getenv("SNAP_PAY_RETURN_TO_THIS_URL")
            return HttpResponseRedirect(
                f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
            )

        except Exception:
            error_message = traceback.format_exc()
            print(error_message)
            if order_receipt:
                order_receipt.azkivam_error_message = error_message
                order_receipt.save()
            failed_stage = "internal_error"
            FRONT_END_RETURN_URL = os.getenv("SNAP_PAY_RETURN_TO_THIS_URL")
            return HttpResponseRedirect(
                f"{FRONT_END_RETURN_URL}?state=FAILED&failed_stage={failed_stage}"
            )
