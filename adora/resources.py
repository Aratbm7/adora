from import_export import resources, fields
from django.contrib.auth import get_user_model
from .models import Order
import jdatetime

User = get_user_model()


class OrderResource(resources.ModelResource):
    # فیلدهای محاسباتی و custom
    row_number = fields.Field(column_name="ردیف", readonly=True)
    user_fullname = fields.Field(column_name="نام کاربر", readonly=True)
    user_phone = fields.Field(column_name="تلفن کاربر", readonly=True)
    jalali_created_at = fields.Field(column_name="تاریخ سفارش (شمسی)", readonly=True)
    jalali_delivery_date = fields.Field(column_name="تاریخ تحویل (شمسی)", readonly=True)
    payment_status_display = fields.Field(column_name="وضعیت پرداخت", readonly=True)
    delivery_status_display = fields.Field(column_name="وضعیت تحویل", readonly=True)
    payment_method_display = fields.Field(column_name="روش پرداخت", readonly=True)
    receiver_choose_display = fields.Field(column_name="نوع گیرنده", readonly=True)

    # فیلدهای محصولات
    products_list = fields.Field(column_name="لیست محصولات", readonly=True)
    products_count = fields.Field(column_name="تعداد محصولات", readonly=True)
    total_items_price = fields.Field(column_name="جمع قیمت محصولات", readonly=True)

    # مبلغ قابل پرداخت
    payable_amount = fields.Field(column_name="مبلغ قابل پرداخت", readonly=True)

    class Meta:
        model = Order
        fields = (
            "row_number",
            "id",
            "tracking_number",
            "user_fullname",
            "user_phone",
            "total_price",
            "delivery_cost",
            "amount_used_wallet_balance",
            "order_reward",
            "payable_amount",
            "payment_status_display",
            "payment_method_display",
            "payment_reference",
            "delivery_status_display",
            "jalali_delivery_date",
            "deliver_post_name",
            "delivery_tracking_url",
            "receiver_full_name",
            "receiver_phone_number",
            "receiver_choose_display",
            # "extra_describtion",
            "jalali_created_at",
            "products_list",
            "products_count",
            "total_items_price",
            "use_wallet_balance",
            "torob_payment_token",
            "snap_payment_token",
            "azkivam_payment_token",
        )
        export_order = (
            "row_number",
            "id",
            "tracking_number",
            "jalali_created_at",
            "user_fullname",
            "user_phone",
            "products_list",
            "products_count",
            "total_items_price",
            "delivery_cost",
            "total_price",
            "amount_used_wallet_balance",
            "order_reward",
            "payable_amount",
            "payment_status_display",
            "payment_method_display",
            "payment_reference",
            "delivery_status_display",
            "jalali_delivery_date",
            "deliver_post_name",
            "delivery_tracking_url",
            "receiver_full_name",
            "receiver_phone_number",
            "receiver_choose_display",
            # "extra_describtion",
            "use_wallet_balance",
        )

    def get_export_queryset(self, request=None):
        """فقط سفارش‌های موفق را export کنیم"""
        # وضعیت‌های موفق پرداخت
        successful_payment_statuses = [
            Order.PAYMENT_STATUS_COMPLETE,  # "C" - موفق
            Order.SNAP_UPDATE,
        ]

        # سفارش‌هایی که پرداخت موفق دارند
        queryset = Order.objects.filter(
            payment_status__in=successful_payment_statuses,
        ).order_by("-created_date")

        return queryset

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.counter = 1

    def dehydrate_row_number(self, order):
        """شماره ردیف"""
        row_num = self.counter
        self.counter += 1
        return row_num

    def dehydrate_user_fullname(self, order):
        """نام کامل کاربر"""
        if order.user and hasattr(order.user, "profile"):
            profile = order.user.profile
            if profile.first_name and profile.last_name:
                return f"{profile.first_name} {profile.last_name}"
            elif order.user.phone_number:
                return order.user.phone_number
        return "نامشخص"

    def dehydrate_user_phone(self, order):
        """تلفن کاربر"""
        if order.user and hasattr(order.user, "phone_number"):
            return str(order.user.phone_number)
        return ""

    def dehydrate_jalali_created_at(self, order):
        """تاریخ شمسی سفارش"""
        if order.created_date:
            try:
                jdate = jdatetime.datetime.fromgregorian(datetime=order.created_date)
                return jdate.strftime("%Y/%m/%d %H:%M")
            except Exception as e:
                print(f"Error converting created_date: {e}")
                return str(order.created_date)
        return ""

    def dehydrate_jalali_delivery_date(self, order):
        """تاریخ شمسی تحویل"""
        if order.delivery_date:
            try:
                return order.delivery_date
            except:
                return str(order.delivery_date)
        return ""

    def dehydrate_payment_status_display(self, order):
        """نمایش وضعیت پرداخت"""
        return dict(Order.PAYMENT_STATUS_CHOICES).get(
            order.payment_status, order.payment_status
        )

    def dehydrate_delivery_status_display(self, order):
        """نمایش وضعیت تحویل"""
        return dict(Order.DELIVERY_STATUS_CHOICES).get(
            order.delivery_status, order.delivery_status
        )

    def dehydrate_payment_method_display(self, order):
        """نمایش روش پرداخت"""
        return dict(Order.PAYMENT_METHOD_CHOICES).get(
            order.payment_method, order.payment_method
        )

    def dehydrate_receiver_choose_display(self, order):
        """نمایش نوع گیرنده"""
        return dict(Order.RECEIVER_CHOICES).get(
            order.receiver_choose, order.receiver_choose
        )

    def dehydrate_products_list(self, order):
        """لیست محصولات به صورت متن"""
        items = order.order_items.select_related("product").all()
        products = []
        for item in items:
            if item.product:
                product_name = item.product.fa_name or "نامشخص"
            else:
                product_name = "نامشخص"
            products.append(f"{product_name} ({item.quantity} عدد)")

        return " | ".join(products) if products else "هیچ محصولی"

    def dehydrate_products_count(self, order):
        """تعداد کل محصولات"""
        return order.order_items.count()

    def dehydrate_total_items_price(self, order):
        """جمع قیمت محصولات بدون هزینه پست"""
        items = order.order_items.all()
        if items:
            total = sum(
                item.sold_price * item.quantity for item in items if item.sold_price
            )
            return f"{total:,.0f}"
        return "0"

    def dehydrate_payable_amount(self, order):
        """مبلغ قابل پرداخت (کل منهای کیف پول)"""
        try:
            total_price = float(order.total_price or 0)
            wallet_balance = float(order.amount_used_wallet_balance or 0)
            payable = total_price - wallet_balance
            return f"{payable:,.0f}"
        except (ValueError, TypeError):
            return "0"
