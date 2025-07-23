import json
import os
import time
import traceback
from urllib import request

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
)
from adora.tasks import get_torobpay_access_token, send_order_status_message
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
            int(os.getenv("ORDER_SUCCESS")),
        )

    def _failed_sms(self, order: Order):
        send_order_status_message.delay(
            str(order.user.phone_number).replace("+98", "0"),
            [self._get_full_name_or_phone_number(order)],
            int(os.getenv("ORDER_FAILED")),
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
                {"message": "Missing required parameters: payment_status, authority, or tracking_number."},
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
                {"message": f"Invalid authority: {authority} does not match this order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment_status == "OK":
            try:
                zarin_verify_url = os.getenv("ZARIN_VERIFY_URL")
                verify_payload = {
                    "merchant_id": os.getenv("ZARIN_MERCHANT_ID"),
                    "amount": int(order.total_price),
                    "authority": authority,
                }

                verify_response = requests.post(
                    zarin_verify_url,
                    headers={"accept": "application/json", "content-type": "application/json"},
                    data=json.dumps(verify_payload),
                )

                if verify_response.status_code != 200:
                    return Response(
                        {"message": "Zarinpal server returned error", "status": verify_response.status_code},
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
                    {"message": "Unexpected response from Zarinpal.", "response": verify_json},
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

            access_token = request.query_params.get("torob_access_token", "")
            tracking_number = request.query_params.get("tracking_number", "")

            if not tracking_number or not access_token:
                return Response(
                    {"message": "Missing required parameters: tracking_number or torob_access_token"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(tracking_number=tracking_number).first()
            if not order:
                return Response(
                    {"message": f"No order found with tracking number {tracking_number}."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not order.torob_payment_token:
                return Response(
                    {"message": "No order payment token found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            order_receipt = order.receipt
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
                transaction_id = verify_data.get("response", {}).get("transactionId", "")
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
                    error_message = settle_data.get("errorData", {}).get("message", "Unknown error")
                    error_code = settle_data.get("errorData", {}).get("errorCode", "Unknown code")
                    order_receipt.torob_error_message = error_message
                    order_receipt.torob_error_code = error_code
                    order_receipt.save()
                    order.payment_status = "F"
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
                error_message = verify_data.get("errorData", {}).get("message", "Unknown error")
                error_code = verify_data.get("errorData", {}).get("errorCode", "Unknown code")
                order_receipt.torob_error_message = error_message
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
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

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

    
    @action(
        detail=False,
        methods=["get"],
        url_path="torobpay-access-token",
        # permission_classes=[permissions.IsAuthenticated],
        permission_classes=[permissions.AllowAny],
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
            access_token = request.query_params.get("torob_access_token", "")

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
                "content-type": "application/json",
                "Authorization": f"Bearer {access_token}",
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

        except Exception:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An unexpected error!!"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ConnectionError:
            error_message = str(traceback.format_exc())
            print(error_message)
            return Response(
                {"message": f"An Cennection error!! Try again please"},
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
            returned_asked_reason = serializer.validated_data[
                "returned_rejected_reason"
            ]
            if not tracking_number:
                return Response(
                    {"message": "Tracking number is missing."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.filter(tracking_number=tracking_number).first()
            self._failed_sms(order)

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


class CashDiscountPercentViewset(ModelViewSet):
    http_method_names = [
        "get",
    ]
    queryset = CashDiscountPercent.objects.all()
    serializer_class = CashDiscountPercentSerializer
    permission_classes = [permissions.AllowAny]
