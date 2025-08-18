import os
from ast import Dict
from decimal import Decimal
from typing import Any, List, LiteralString

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework.exceptions import ValidationError

from adora.models import (
    FAQ,
    Brand,
    Car,
    CashDiscountPercent,
    Category,
    Collaborate_Contact,
    Comment,
    Matrial,
    Order,
    OrderItem,
    Post,
    PostImage,
    Product,
    ProductImage,
)
from adora.tasks import (
    azkivam_send_create_ticket_request,
    send_torobpay_payment_information,
    send_zarin_payment_information,
)
from rest_framework import serializers


class CarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        exclude = ("created_date", "updated_date")


# class CategorySeriali
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        # fields = ('id', 'alt', 'image_url', 'product')
        exclude = ("created_date", "updated_date")


class CategoryWhitChildrenSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "image", "alt", "parent", "children"]

    def get_parent(self, obj):
        # If parent exists, return its serialized data using the same serializer
        if obj.parent:
            # return CategorySerializer(obj.parent).data
            return obj.parent.name
        return None

    def get_children(self, obj):
        children = obj.children.all()
        return CategoryWhitChildrenSerializer(children, many=True).data


class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "image",
            "alt",
            "parent",
        ]

    def get_parent(self, obj):
        # If parent exists, return its serialized data using the same serializer
        if obj.parent:
            # return CategorySerializer(obj.parent).data
            return obj.parent.name
        return None


class SimilarProductsSerializer(serializers.ModelSerializer):
    # category = serializers.SerializerMethodField(read_only=True)
    # material = serializers.SerializerMethodField(read_only=True)
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    brand = serializers.SerializerMethodField(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    wallet_discount_percent = serializers.CharField(source="wallet_discount")

    class Meta:
        model = Product
        fields = [
            "id",
            "fa_name",
            "en_name",
            "price",
            "price_discount_percent",
            "discounted_price",
            "wallet_discount_percent",
            "discounted_wallet",
            "count",
            "new",
            #   'material',
            #   'category',
            "compatible_cars",
            "brand",
            "images",
            #   'description',
            "buyer",
            "customer_point",
        ]

    def get_brand(self, obj):
        return {
            "id": obj.brand.id,
            "name": obj.brand.name,
            "image_url": obj.brand.image,
            "alt": obj.brand.alt,
        }

    def get_category(self, obj):
        return {
            "id": obj.category.id,
            "name": obj.category.name,
            "image_url": obj.category.image,
            "alt": obj.category.alt,
        }

    def get_material(self, obj):
        return {"id": obj.material.id, "name": obj.material.material_name}

    def get_compatible_cars(self, obj):
        return [
            {
                "id": car.id,
                "fa_name": car.fa_name,
                "image_url": car.image,
                "image_alt": car.alt,
            }
            for car in obj.compatible_cars.all()
        ]

    def get_discounted_price(self, obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)

    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100


class MaterialSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="material_name")

    class Meta:
        model = Matrial
        fields = ["id", "name"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        # fields = '__all__'
        exclude = ["created_date", "updated_date", "alt"]


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField(
        read_only=True
    )  # Marking user as read-only with custom logic

    class Meta:
        model = Comment
        fields = (
            "id",
            "user",
            "product",
            "parent",
            "text",
            "rating",
            "buy_suggest",
            "created_date",
            "updated_date",
            "replies",
        )

    def get_replies(self, obj):
        replies = obj.replies.all()  # Fetch all replies to the current comment
        return CommentSerializer(replies, many=True).data  # Serialize each reply

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

    def get_user(self, obj):
        # profile = getattr(obj.user,'profile', None)
        # if profile and profile.first_name:

        return {
            "full_name": f"{obj.user.profile.first_name} {obj.user.profile.last_name}",
            "id": obj.user.id,
        }


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer"]


class ProductSearchSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "fa_name",
            "images",
        )


class ProductOrderItemSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    wallet_discount_percent = serializers.CharField(source="wallet_discount")
    # main_category = CategorySerializer(read_only=True, source='category')
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # brand= BrandSerializer(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "custom_id",
            "fa_name",
            "en_name",
            "price",
            "price_discount_percent",
            "discounted_price",
            "wallet_discount_percent",
            "discounted_wallet",
            "count",
            "install_location",
            "guarantee",
            "new",
            "best_seller",
            "compatible_cars",
            "images",
        )

    def get_discounted_price(self, obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)

    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100

    def get_compatible_cars(self, obj):
        return [
            {
                "id": car.id,
                "fa_name": car.fa_name,
                "image_url": car.image,
                "image_alt": car.alt,
            }
            for car in obj.compatible_cars.all()
        ]


class ProductRetrieveSerializer(serializers.ModelSerializer):
    faqs = serializers.SerializerMethodField()

    # main_category = serializers.CharField(source='category.fa_name', read_only=True)
    # comments = CommentSerializer(read_only=True, many=True)
    comments = serializers.SerializerMethodField()
    main_category = CategorySerializer(read_only=True, source="category")
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # image = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    # brand= serializers.SerializerMethodField(read_only=True)
    brand = BrandSerializer(read_only=True)
    similar_products = SimilarProductsSerializer(many=True)
    images = ProductImageSerializer(many=True, read_only=True)
    wallet_discount_percent = serializers.CharField(source="wallet_discount")
    category_hierarchy = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "custom_id",
            "fa_name",
            "en_name",
            "price",
            "price_discount_percent",
            "discounted_price",
            "wallet_discount_percent",
            "discounted_wallet",
            "count",
            "install_location",
            "count_in_box",
            "guarantee",
            "guarantee_duration",
            "new",
            "size",
            "main_category",
            "compatible_cars",
            "similar_products",
            "brand",
            "images",
            "best_seller",
            "title_description",
            "packing_description",
            "shopping_description",
            "buyer",
            "customer_point",
            "comments",
            "category",
            "faqs",
            "category_hierarchy",
        ]

    def get_comments(self, obj):
        comments = obj.comments.filter(parent__isnull=True)
        return CommentSerializer(comments, many=True).data

    def get_category(self, obj):
        return {
            "id": obj.category.id,
            "name": obj.category.name,
            "image_url": obj.category.image,
            "alt": obj.category.alt,
        }

    def get_material(self, obj):
        return {"id": obj.material.id, "name": obj.material.material_name}

    def get_compatible_cars(self, obj):
        return [
            {
                "id": car.id,
                "fa_name": car.fa_name,
                "image_url": car.image,
                "image_alt": car.alt,
            }
            for car in obj.compatible_cars.all()
        ]

    def get_discounted_price(self, obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)

    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100

    # def get_similar_products(self, obj):
    #     return ProductSerializer(obj.similar_products.all(), many=True).data

    # def validate_price(self, value):
    #     try:
    #         # Validate the price field
    #         return value
    #     except ValidationError as e:
    #         raise serializers.ValidationError("Custom error message for price validation")

    def get_faqs(self, obj):
        """
        دریافت سوالات عمومی و اختصاصی محصول
        """
        faqs = obj.get_all_faqs()
        return FAQSerializer(faqs, many=True).data

    def get_category_hierarchy(self, obj):
        return obj.category.get_hierarchy()


class ProductListSerializer(serializers.ModelSerializer):
    main_category = CategorySerializer(read_only=True, source="category")
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # image = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    comments = serializers.SerializerMethodField()
    # brand= serializers.SerializerMethodField(read_only=True)
    brand = BrandSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    wallet_discount_percent = serializers.CharField(source="wallet_discount")

    class Meta:
        model = Product
        fields = [
            "id",
            "custom_id",
            "fa_name",
            "en_name",
            "price",
            "price_discount_percent",
            "discounted_price",
            "wallet_discount_percent",
            "discounted_wallet",
            "count",
            "install_location",
            "count_in_box",
            "guarantee",
            "best_seller",
            "guarantee_duration",
            "new",
            "size",
            "main_category",
            "compatible_cars",
            "brand",
            "images",
            "title_description",
            "packing_description",
            "shopping_description",
            "buyer",
            "customer_point",
            "comments",
        ]

    # def get_brand(self, obj):
    #     return {'id': obj.brand.id, 'name': obj.brand.name, 'image_url': obj.brand.image, 'alt': obj.brand.alt}

    def get_comments(self, obj):
        comments = obj.comments.filter(parent__isnull=True)
        return CommentSerializer(comments, many=True).data

    def get_category(self, obj):
        return {
            "id": obj.category.id,
            "name": obj.category.name,
            "image_url": obj.category.image,
            "alt": obj.category.alt,
        }

    def get_material(self, obj):
        return {"id": obj.material.id, "name": obj.material.material_name}

    def get_compatible_cars(self, obj):
        return [
            {
                "id": car.id,
                "fa_name": car.fa_name,
                "image_url": car.image,
                "image_alt": car.alt,
            }
            for car in obj.compatible_cars.all()
        ]

    def get_discounted_price(self, obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)

    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100

    # def validate(self, data):
    #     product = data.get('product')
    #     if product and Comment.objects.filter(product=product).count() >= 5:
    #         raise serializers.ValidationError("A product cannot have more than 5 comments")
    #     return datam


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "product", "quantity", "sold_price")


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True)
    amount_used_wallet_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0, read_only=True
    )
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0, read_only=True
    )
    order_reward = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0, read_only=True
    )
    tracking_number = serializers.CharField(max_length=20, read_only=True)
    payment_status = serializers.CharField(read_only=True)
    delivery_status = serializers.CharField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "tracking_number",
            "payment_status",
            "payment_method",
            "payment_reference",
            "delivery_status",
            "delivery_date",
            "delivery_address",
            "delivery_cost",
            "total_price",
            "use_wallet_balance",
            "amount_used_wallet_balance",
            "order_reward",
            "extra_describtion",
            "receiver_phone_number",
            "receiver_full_name",
            "receiver_choose",
            "user",
            "order_items",
            "delivery_tracking_url",
            "deliver_post_name",
            "created_date",
            "updated_date",
            "returned_status",
            "returned_rejected_reason",
            "returned_asked_reason",
            "torob_payment_page_url",
            "torob_payment_token",
        )

    def calculate_total_price_for_cahs_purchase(self, order: Order):
        """This method calculates the total price for cash purchase orders.
        It applies the cash_discount_percent to the total price of the order items
        and adds the delivery cost.


        Args:
            order (Order)
        """
        cash_discount_percent = CashDiscountPercent.objects.last()

        total = sum([item.get_total() for item in order.order_items.all()])
        if cash_discount_percent:
            print(
                "zarinpal_discount_percent",
                cash_discount_percent.zarinpal_discount_percent,
            )
            total -= (total * cash_discount_percent.zarinpal_discount_percent) / 100
        else:
            print("Cash Discoutn Percent not found (message from order serizlier)")

        order.total_price = total + order.delivery_cost
        order.save()

    def calculate_total_price_for_Installment_purchase(self, order: Order):
        """This mehtod calculates the total price for installment purchase orders.

        Args:
            order (Order)
        """
        total = sum([item.get_total() for item in order.order_items.all()])
        order.total_price = total + order.delivery_cost
        order.save()

    def calculate_order_reward(self, order):
        """_summary_
        This reward calculated by each order item and saved in user
        wallet
        """
        total_reward = sum(
            [item.get_wallet_reward() for item in order.order_items.all()]
        )
        order.order_reward = total_reward
        order.save()

    def _get_wallet_balance(sel, order) -> Decimal:
        return order.user.profile.wallet_balance

    def use_user_walet_balance_in_order(self, order):
        """This method use mines wallet balance from total price"""
        wallet_balance = self._get_wallet_balance(order)

        order.amount_used_wallet_balance = wallet_balance
        order.total_price -= wallet_balance
        order.save()

    def create(self, validated_data):
        order_items_data: List[dict[str, Any]] = validated_data.pop("order_items")
        # print("order_items_data", order_items_data)
        # print('sold_pric', order_items_data[0]['sold_price'])
        request = self.context.get("request")
        # if not request:
        #     torob_access_token = "There is no Torob Access Token"
        # torob_access_token = request.query_params.get("torob_access_token")

        try:
            # Wrap everything in a transaction to ensure atomicity
            with transaction.atomic():
                # Create the order
                order = Order.objects.create(**validated_data)
                # Create the order items in bulk

                for item_data in order_items_data:
                    order_item = OrderItem(
                        order=order,
                        product=item_data["product"],
                        quantity=item_data["quantity"],
                    )
                    order_item.save()  # ذخیره‌سازی به‌صورت معمولی، که متد save فراخوانی می‌شود

                if order.payment_reference == os.getenv("ZARIN_MERCHANT_NAME"):
                    # Calculate total price for cash purchase
                    self.calculate_total_price_for_cahs_purchase(order)
                    # Save order reward to user's wallet
                    self.calculate_order_reward(order)
                    send_zarin_payment_information(order)
                    print("hello_zarin")

                if order.payment_reference == os.getenv("TOROBPAY_MERCHANT_NAME"):
                    self.calculate_total_price_for_Installment_purchase(order)
                    print("helllo_torob")
                    send_torobpay_payment_information(order)

                if order.payment_reference == os.getenv("AZKIVAM_MERHCHANT_NAME"):
                    self.calculate_total_price_for_Installment_purchase(order)
                    print("hello_azkivam")
                    azkivam_send_create_ticket_request(order)

                # Use wallet_balance
                if order.use_wallet_balance:
                    print(" order.use_wallet_balance", order.use_wallet_balance)
                    self.use_user_walet_balance_in_order(order)


            return order

        except IntegrityError as e:
            # Handle IntegrityError (e.g., unique constraints or foreign key issues)
            raise ValidationError({"detail": f"Database integrity error: {str(e)}"})

        except Exception as e:
            # Catch any other exceptions and return an appropriate error message
            raise ValidationError({"detail": f"An error occurred: {str(e)}"})

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "phone_number": str(obj.user.phone_number),
            "full_name": f"{obj.user.profile.first_name} {obj.user.profile.last_name}",
        }


class OrderListItemSerializer(serializers.ModelSerializer):
    product = ProductOrderItemSerializer()

    class Meta:
        model = OrderItem
        fields = ("id", "product", "quantity")


class OrderListSerializer(serializers.ModelSerializer):
    order_items = OrderListItemSerializer(many=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "tracking_number",
            "payment_status",
            "payment_method",
            "payment_reference",
            "delivery_status",
            "delivery_date",
            "delivery_address",
            "deliver_post_name",
            "delivery_cost",
            "total_price",
            "use_wallet_balance",
            "amount_used_wallet_balance",
            "order_reward",
            "extra_describtion",
            "receiver_phone_number",
            "receiver_full_name",
            "receiver_choose",
            "user",
            "order_items",
            "created_date",
            "updated_date",
            "returned_status",
            "returned_rejected_reason",
            "returned_asked_reason",
        )

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "phone_number": str(obj.user.phone_number),
            "full_name": f"{obj.user.profile.first_name} {obj.user.profile.last_name}",
        }


class AuthorSerilizer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = get_user_model()
        fields = ("id", "full_name", "date_joined")

    def get_full_name(self, obj):
        if not obj.profile:
            return "کاربر آدورا یدک"
        return f"{obj.profile.first_name} {obj.profile.last_name}"


class ProductBlogSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    wallet_discount_percent = serializers.CharField(source="wallet_discount")
    # main_category = CategorySerializer(read_only=True, source='category')
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # brand= BrandSerializer(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "fa_name",
            "price",
            "price_discount_percent",
            "discounted_price",
            "wallet_discount_percent",
            "discounted_wallet",
            "install_location",
            "new",
            "compatible_cars",
            "images",
        )

    def get_discounted_price(self, obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)

    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100

    def get_compatible_cars(self, obj):
        return [
            {
                "id": car.id,
                "fa_name": car.fa_name,
                "image_url": car.image,
                "image_alt": car.alt,
            }
            for car in obj.compatible_cars.all()
        ]


class PostImageSerilizer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ("id", "alt", "image_url")


class PostSerializer(serializers.ModelSerializer):

    related_products = ProductBlogSerializer(many=True, read_only=True)
    authors = AuthorSerilizer(many=True, read_only=True)
    images = PostImageSerilizer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = (
            "id",
            "title",
            "slug",
            "authors",
            "related_products",
            "images",
            "content",
            "created_date",
            "updated_date",
            "status",
        )


class CollaborateAndContactUsSerializer(serializers.ModelSerializer):
    phone_number = PhoneNumberField()

    class Meta:
        model = Collaborate_Contact
        fields = "__all__"


class ProductTorobSerilizers(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="pk", read_only=True)
    page_url = serializers.SerializerMethodField(read_only=True)
    price = serializers.SerializerMethodField(read_only=True)
    old_price = serializers.IntegerField(source="price", read_only=True)
    availability = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = ["product_id", "page_url", "old_price", "availability", "price"]

    def get_page_url(self, obj: Product) -> str:
        product_title = obj.fa_name.strip().replace(" ", "-")
        return f"https://adorayadak.ir/product/adp-{obj.id}/{product_title}"

    def get_price(self, obj: Product) -> int:
        discount_percent = int(obj.price_discount_percent)
        price = obj.price

        return int(price * (1 - discount_percent / 100))

    def get_availability(self, obj: Product) -> str:
        count = obj.count
        if count > 0:
            return "instock"
        return "outofstock"


class ProductEmallsSerilizers(serializers.ModelSerializer):
    title = serializers.CharField(source="fa_name", read_only=True)
    url = serializers.SerializerMethodField(read_only=True)
    price = serializers.SerializerMethodField(read_only=True)
    old_price = serializers.IntegerField(source="price", read_only=True)
    is_available = serializers.SerializerMethodField(read_only=True)
    category = serializers.SerializerMethodField(read_only=True)
    image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "url",
            "old_price",
            "is_available",
            "price",
            "category",
            "image",
        ]

    def get_url(self, obj: Product) -> str:
        product_title = obj.fa_name.strip().replace(" ", "-")
        return f"https://adorayadak.ir/product/adp-{obj.id}/{product_title}"

    def get_price(self, obj: Product) -> int:
        discount_percent = int(obj.price_discount_percent)
        price = obj.price

        return int(price * (1 - discount_percent / 100))

    def get_is_available(self, obj: Product) -> bool:
        count = obj.count
        if count > 0:
            return True
        return False

    def get_category(self, obj: Product) -> str:
        return obj.category.name

    def get_image(self, obj: Product) -> str | None:
        all_images = obj.images.all()
        if not all_images:
            return None
        return str(all_images[0].image_url)


class OrderRejectedReasonSerializer(serializers.ModelSerializer):

    class Meta:
        model = Order
        fields = ["returned_rejected_reason"]


class CashDiscountPercentSerializer(serializers.ModelSerializer):

    class Meta:
        model = CashDiscountPercent
        fields = ["zarinpal_discount_percent"]
