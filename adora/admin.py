import os

from admin_auto_filters.filters import AutocompleteFilter
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from jalali_date.admin import ModelAdminJalaliMixin

from adora.models import *
from adora.tasks import send_order_status_message
from core.utils.separate_and_convert_to_fa import separate_digits_and_convert_to_fa
from core.utils.show_jalali_datetime import show_date_time

admin.site.site_header = "پنل ادمین آدورا یدک"
admin.site.site_title = "پنل ادمین آدورا یدک"
admin.site.index_title = " پنل ادمین آدورا یدک"

# admin.site.register(Matrial)
admin.site.register(OrderProvider)
admin.site.register(Banner)
admin.site.register(Post)
admin.site.register(PostImage)
admin.site.register(CashDiscountPercent)


def get_full_name_or_default_name(order: Order) -> str:
    user_prfile = order.user.profile
    name = user_prfile.first_name or ""
    last_name = user_prfile.last_name or ""
    full_name = f"{name} {last_name}"
    if full_name.strip():
        return full_name.strip()

    # return str(order.user.phone_number).replace("+98", "0")
    return "کاربر آدورا یدک"


class UserFilter(AutocompleteFilter):
    title = _("شماره تلفن")
    field_name = "user"
    text_help = _("توجه کنید که شماره با +۹۸ ذخیره شده است.")


class OrderItemInline(admin.StackedInline):
    model = OrderItem


class OrderAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    search_fields = [
        "tracking_number",
        "user__profile__first_name",
        "user__profile__last_name",
    ]
    list_display = [
        "tracking_number",
        "view_items_link",
        "user_link",
        "profile_link",
        "payment_status",
        "delivery_status",
        "get_total_price",
        "get_amount_used_wallet_balance",
        "receipt_link",
        "get_created_date",
        "use_wallet_balance",
    ]
    readonly_fields = ("get_created_date", "get_updated_date")
    search_help_text = _(
        "شما میتواند با   شماره پیگیری و نام و نام خانوادگی پروفایل سفارش را جستجو کنید "
    )
    list_filter = (
        UserFilter,
        "payment_status",
        "delivery_status",
        "use_wallet_balance",
    )

    inlines = (OrderItemInline,)

    def get_excluded_fields(self):
        """Returns fields that should be excluded from 'Order Details'."""
        return {*self.readonly_fields, "id", "created_date", "updated_date"}

    def get_order_fields(self):
        """Returns all fields of the Order model excluding specified fields."""
        return [
            field.name
            for field in Order._meta.fields
            if field.name not in self.get_excluded_fields()
        ]

    def get_fieldsets(self, request, obj=None):
        """Dynamically generates fieldsets."""
        return (
            (
                "تاریخ‌های ثبت و بروزرسانی",
                {  # This section appears first
                    "fields": self.readonly_fields,
                },
            ),
            (
                "جزئیات سفارش",
                {  # This section contains all fields dynamically
                    "fields": self.get_order_fields(),
                },
            ),
        )

    @admin.display(description="هزینه کل سفارش (تومان)")
    def get_total_price(self, obj):
        return separate_digits_and_convert_to_fa(obj.total_price)

    @admin.display(description="پاداش استفاده شده (تومان)")
    def get_amount_used_wallet_balance(self, obj):
        return separate_digits_and_convert_to_fa(obj.amount_used_wallet_balance)

    @admin.display(description="رسید")
    def receipt_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/orderreceipt/{obj.receipt.id}/change",
            f"{obj.receipt.error_msg if obj.receipt.error_msg else 'OK'} ",
        )

    @admin.display(description="آیتم های سفارش")
    def view_items_link(self, obj):
        url = reverse("admin:adora_orderitem_changelist")
        return format_html(
            '<a href="{}?order__id={}">مشاهده جزئیات سفارش</a>', url, obj.id
        )

    @admin.display(description="پروفایل")
    def profile_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/profile/{obj.user.profile.id}/change",
            f"{obj.user.profile.first_name} {obj.user.profile.last_name}",
        )

    @admin.display(description="کاربر")
    def user_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/user/{obj.user.id}/change",
            str(obj.user.phone_number).replace("+98", "0"),
        )

    @admin.display(description="تاریخ ایجاد سفارش")
    def get_created_date(self, obj):
        return show_date_time(obj.created_date)

    @admin.display(description="تاریخ آپدیت")
    def get_updated_date(self, obj):

        # updated_date = datetime.combine(obj.updated_date , datetime.min.time())
        return show_date_time(obj.updated_date)

    def save_model(self, request, obj: Order, form, change):
        # Check if this is an update and not a new object creation
        if change:
            # Get the previous state of the object from the database
            previous_obj: Order = self.model.objects.get(pk=obj.pk)
            # Check if `delivery_status` has changed
            # print(previous_obj.delivery_status)
            full_name = get_full_name_or_default_name(obj)
            phone_number = str(obj.user.phone_number).replace("+98", "0")
            order_traking_number = obj.tracking_number
            # print(phone_number)
            order_delivery_traking_num = obj.delivery_tracking_url
            deliver_post_name = obj.deliver_post_name

            if previous_obj.delivery_status != obj.delivery_status:
                # Call `send_message` if the new status is 'shipped' or 'pending'
                if obj.delivery_status == "P":
                    text_code = os.environ.get("ORDER_PENDING")
                    send_order_status_message.delay(
                        phone_number,
                        [
                            full_name,
                            order_traking_number,
                        ],
                        int(text_code),
                    )
                    # print(text_code)
                if obj.delivery_status == "S":
                    text_code = os.environ.get("ORDER_SHIPPED")
                    send_order_status_message.delay(
                        phone_number,
                        [
                            full_name,
                            order_traking_number,
                            deliver_post_name,
                            order_delivery_traking_num,
                        ],
                        int(text_code),
                    )

                if obj.delivery_status == "D":
                    text_code = os.environ.get("ORDER_DELIVERED")
                    send_order_status_message.delay(
                        phone_number,
                        [
                            full_name,
                            order_traking_number,
                        ],
                        int(text_code),
                    )

            rejected_reason = obj.returned_rejected_reason
            if previous_obj.returned_status != obj.returned_status:

                if obj.returned_status == "RC":
                    text_code = os.environ.get("ORDER_RETURNED_CONFIRM")
                    send_order_status_message.delay(
                        phone_number,
                        [
                            full_name,
                            order_traking_number,
                        ],
                        int(text_code),
                    )

                if obj.returned_status == "RR":
                    text_code = os.environ.get("ORDER_RETURNED_REJECT")
                    send_order_status_message.delay(
                        phone_number,
                        [
                            full_name,
                            order_traking_number,
                            rejected_reason,
                        ],
                        int(text_code),
                    )

        # Proceed with the default save behavior
        super().save_model(request, obj, form, change)


class OrderFilter(AutocompleteFilter):
    titile = _("سفارش")
    field_name = "order"


class OrderItemAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("order_link", "get_product", "quantity", "get_sold_price")
    list_filter = (OrderFilter,)
    search_fields = ("product__fa_name", "product__en_name")
    search_help_text = _("فقط میتوانید با نام فارسی و انگلیسی محصول سرچ کنید.")

    @admin.display(description="شماره پیگیری سفارش")
    def order_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/order/{obj.order.id}/change",
            obj.order.tracking_number,
        )

    @admin.display(description="قیمت فروخته شده")
    def get_sold_price(self, obj):
        return separate_digits_and_convert_to_fa(obj.sold_price)

    @admin.display(description=_("محصول"))
    def get_product(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/product/{obj.product.id}/change",
            obj.product.fa_name,
        )

    order_link.allow_tags = True


class CategoryFilter(AutocompleteFilter):
    title = _("دسته بندی")
    field_name = "category"


class BrandFilter(AutocompleteFilter):
    title = _("شرکت سازنده")
    field_name = "brand"


class StockFilter(admin.SimpleListFilter):
    title = _("وضعیت موجودی")
    parameter_name = "count_in_box"

    def lookups(self, request, model_admin):
        return [("in_stock", _("موجود")), ("out_of_stock", _("نا موجود"))]

    def queryset(self, request, queryset):
        if self.value() == "in_stock":
            return queryset.filter(count_in_box__gt=0)

        if self.value() == "out_of_stock":
            return queryset.filter(count_in_box=0)

        return queryset


class CompatibleCarsFilter(AutocompleteFilter):
    title = _("خودرو مناسب")
    field_name = "compatible_cars"


class ProductImageInline(admin.StackedInline):
    model = ProductImage
    show_change_link = "__all__"


class ProductAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        "fa_name",
        "en_name",
        "get_category",
        "get_brand",
        "new",
        "best_seller",
        "get_images",
        "get_similar_products",
        "get_price",
    )
    search_fields = ("fa_name", "en_name")
    search_help_text = _("شما میتوانید با نام فارسی و انگلیسی سرچ کنید.")
    list_filter = (
        CategoryFilter,
        BrandFilter,
        StockFilter,
        CompatibleCarsFilter,
        "best_seller",
        "new",
        "size",
    )
    inlines = (ProductImageInline,)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "faqs":
            kwargs["queryset"] = FAQ.objects.filter(is_global=False)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description="قیمت (با تخفیف)")
    def get_price(self, obj):
        return separate_digits_and_convert_to_fa(
            obj.price - ((obj.price * obj.price_discount_percent) / 100)
        )

    @admin.display(description="دسته بندی")
    def get_category(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/category/{obj.category.id}/change",
            obj.category.name,
        )

    @admin.display(description="شرکت سازنده")
    def get_brand(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/brand/{obj.brand.id}/change",
            obj.brand.name,
        )

    @admin.display(description="محصولات مشابه")
    def get_similar_products(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/product/?similar_products__id__exact={obj.id}",
            "محصولات مشابه",
        )

    @admin.display(description=_("عکس های محصول"))
    def get_images(self, obj):
        return format_html(
            '<a target=_blank href="{}">{}</a>',
            f"/admin/adora/productimage/?product__id__exact={obj.id}",
            "لینک عکس ها",
        )


class CategoryAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "parent",
        "get_image",
        "get_products",
    )
    search_fields = ("name",)
    search_help_text = _("فقط با نام دسته بندی میتوانید سرچ کنید")
    list_filter = ("parent",)

    @admin.display(description=_("لیست محصولات"))
    def get_products(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/product/?category__id__exact={obj.id}",
            "محصولات",
        )

    @admin.display(description=_("عکس دسته بندی"))
    def get_image(self, obj):
        return format_html('<a target=_blank href="{}">{}</a>', obj.image, "عکس")


class BrandAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("name", "abbreviation", "get_image", "get_products")
    search_fields = ("name",)
    search_help_text = _("فقط میتوانید با نام برند سرچ کنید.")

    @admin.display(description=_("لیست محصولات"))
    def get_products(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/product/?brand__id__exact={obj.id}",
            "محصولات",
        )

    @admin.display(description=_("عکس برند"))
    def get_image(self, obj):
        return format_html('<a target=_blank href="{}">{}</a>', obj.image, "عکس")


class CarAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("fa_name", "get_image", "get_products")
    search_fields = ("fa_name",)
    search_help_text = _("فقط میتوانید با نام برند سرچ کنید.")

    @admin.display(description=_("لیست محصولات"))
    def get_products(self, obj):
        return format_html(
            '<a  href="{}">{}</a>',
            f"/admin/adora/product/?compatible_cars__id__exact={obj.id}",
            "محصولات",
        )

    @admin.display(description=_("عکس خودرو"))
    def get_image(self, obj):
        return format_html('<a target=_blank href="{}">{}</a>', obj.image, "عکس")


class Collabrate_ContactAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("full_name", "get_phone_number", "request_type")
    list_filter = ("request_type",)
    search_fields = ("full_name", "phone_number")
    search_help_text = _("شما میتوانید با نام و نام خانوادگی و شماره تلفن سرچ کنید.")

    @admin.display(description=_("موبایل"))
    def get_phone_number(self, obj):
        return str(obj.phone_number).replace("+98", "0")


class OrderReceiptAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        "get_authority",
        "request_code",
        "verify_code",
        "ref_id",
        "request_msg",
        "get_fee",
        "fee_type",
        "card_pan",
        "get_order",
    )
    list_filter = ("fee_type",)

    @admin.display(description=_("مالیات (تومان)"))
    def get_fee(self, obj):
        return separate_digits_and_convert_to_fa(obj.fee)

    @admin.display(description="Authority")
    def get_authority(self, obj):
        if obj and obj.authority:
            return f"Zarin Pal:{obj.authority[:3]} ... {obj.authority[-10:]}"
        elif obj and obj.torob_reciept:
            return "Torob Pay"
        return "-"

    @admin.display(description=_("سفارش"))
    def get_order(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/order/{obj.order.id}/change",
            obj.order,
        )

    def get_fieldsets(self, request, obj=None):
        """Dynamically generates fieldsets."""
        return (
            (
                "رسید پرداخت ترپ پی",
                {  # This section appears first
                    "fields": (
                        "torob_transaction_id",
                        "torob_error_message",
                        "torob_error_code",
                        "torob_reciept",
                    ),
                },
            ),
            (
                "رسید پرداخت زرین پال",
                {  # This section contains all fields dynamically
                    "fields": (
                        "authority",
                        "request_code",
                        "verify_code",
                        "ref_id",
                        "request_msg",
                        "fee_type",
                        "fee",
                        "card_pan",
                        "connection_error",
                    ),
                },
            ),
        )


class ProductImageAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("alt", "get_image", "get_same_images")
    search_fields = ("alt", "product__en_name")
    search_help_text = _("میتوانید با اسم فارسی و انگلیسی عکس محصول را سرچ کنید.")

    @admin.display(description=_("فیلتر با محصول یکسان"))
    def get_same_images(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/productimage/?product__id__exact={obj.product.id}",
            "عکس های یکسان",
        )

    @admin.display(description=_("لینک عکس"))
    def get_image(self, obj):
        return format_html('<a target=_blank href="{}">{}</a>', obj.image_url, "عکس")


class CommentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        "get_text",
        "user_link",
        "profile_link",
        "get_created_date",
        "get_updated_date",
    )
    search_fields = [
        "user__phone_number",
        "user__profile__first_name",
        "user__profile__last_name",
    ]
    search_help_text = _(
        "شما میتواند با شماره تلفن (چهار رقم اخر و انگلیسی) و نام و نام خانوادگی سرچ کنید."
    )
    list_filter = ("rating", "buy_suggest")

    @admin.display(description=_("متن پیام"))
    def get_text(self, obj):
        return f"{obj.text[:25]} ... "

    @admin.display(description="کاربر")
    def user_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/user/{obj.user.id}/change",
            str(obj.user.phone_number).replace("+98", "0"),
        )

    @admin.display(description="پروفایل")
    def profile_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/profile/{obj.user.profile.id}/change",
            f"{obj.user.profile.first_name} {obj.user.profile.last_name}",
        )

    @admin.display(description="تاریخ و ساعت ایجاد کامنت")
    def get_created_date(self, obj):
        return show_date_time(obj.created_date)

    @admin.display(description="تاریخ و ساعت آپدیت")
    def get_updated_date(self, obj):
        return show_date_time(obj.updated_date)


class FAQAdmin(admin.ModelAdmin):
    list_display = ("get_question", "get_answer", "is_global")
    list_filter = ("is_global",)
    search_fields = ("question",)
    search_help_text = _("میتوانید با سوال سرچ کنید")

    @admin.display(description=_("سوال"))
    def get_question(self, obj):
        return f"{obj.question[:20]} ..."

    @admin.display(description=_("جواب"))
    def get_answer(self, obj):
        return f"{obj.answer[:20]} ..."


class SMSCampaignParamForm(forms.ModelForm):
    class Meta:
        model = SMSCampaignParam
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        is_static = cleaned_data.get("is_static")
        value_source = cleaned_data.get("value_source")
        static_value = cleaned_data.get("static_value")

        if is_static and value_source:
            raise ValidationError(
                "اگر تیک فیلد (مقدار ثابت) باشد باید فیلد (مسیر پارامتر ورودی پیامک) خالی باشد و برعکس."
            )

        if is_static and not static_value:
            raise ValidationError(
                "اگر تیک فیلد (مقدار ثابت) فعال باشد باید مقدار ثابت نیز خالی نباشد."
            )

        if not is_static and not value_source:
            raise ValidationError("اگر مقدار ثابت نیست باید مسیر پارامتر وارد شود.")

        return cleaned_data


class SMSCampaignFilter(AutocompleteFilter):
    title = _("کمپین")
    field_name = "campaign"


class UserFilter(AutocompleteFilter):
    title = _("کاربر")
    field_name = "user"


class SMSCampaignParamAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    form = SMSCampaignParamForm
    list_display = ("get_param_value", "get_campaign_name", "position")
    list_filter = (SMSCampaignFilter,)

    @admin.display(description=_("مقدار پارامتر"))
    def get_param_value(self, obj: SMSCampaignParam) -> str:
        if obj.value_source:
            return dict(settings.ALLOWED_SMS_CAMPAIGN_PARAM_PATHS).get(
                obj.value_source, obj.value_source
            )
        return f"مقدار ثابت :‌ {obj.static_value}"

    @admin.display(description=_("نام کمپین"))
    def get_campaign_name(self, obj: SMSCampaignParam) -> str:
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/smscampaign/{obj.campaign.id}/change",
            obj.campaign.name,
        )


class SMSCampaignParamInline(admin.StackedInline):
    model = SMSCampaignParam
    show_change_link = "__all__"


class SMSCampaignAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("name", "sms_template_id", "is_active", "get_params")
    inlines = (SMSCampaignParamInline,)
    search_fields = ("name",)
    list_filter = ("name", "is_active")

    @admin.display(description=_("پارامتر های کمپین"))
    def get_params(self, obj: SMSCampaign):
        return format_html(
            '<a target=_blank href="{}">{}</a>',
            f"/admin/adora/smscampaignparam/?campaign__id__exact={obj.id}",
            "لینک پارامتر ها ",
        )


class SMSCampaignSendLogAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        "get_args",
        "get_campaign",
        "get_user",
        "status_code",
        "response_message",
        "get_sent_at",
        "is_successful",
    )
    list_filter = (SMSCampaignFilter, UserFilter, "is_successful", "sent_at")

    @admin.display(description=_("تاریخ ارسال"))
    def get_sent_at(self, obj: SMSCampaignSendLog):
        return show_date_time(obj.sent_at)

    @admin.display(description=_("آرگومان های ارسال شده"))
    def get_args(self, obj: SMSCampaignSendLog):
        cleaned = obj.message_args.replace("'", "").replace('"', "")
        return f"{cleaned[1:20]} ..."

    @admin.display(description=_("نام کمپین"))
    def get_campaign(self, obj: SMSCampaignSendLog) -> str:
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/smscampaign/{obj.campaign.id}/change",
            obj.campaign.name,
        )

    @admin.display(description=_("کاربر"))
    def get_user(self, obj: SMSCampaignSendLog) -> str:
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/user/{obj.user.id}/change",
            obj.user.profile.get_full_name,
        )


admin.site.register(SMSCampaign, SMSCampaignAdmin)
admin.site.register(SMSCampaignParam, SMSCampaignParamAdmin)
admin.site.register(SMSCampaignSendLog, SMSCampaignSendLogAdmin)

admin.site.register(Comment, CommentAdmin)
admin.site.register(OrderReceipt, OrderReceiptAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ProductImage, ProductImageAdmin)
admin.site.register(FAQ, FAQAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Brand, BrandAdmin)
admin.site.register(Car, CarAdmin)
admin.site.register(Collaborate_Contact, Collabrate_ContactAdmin)
