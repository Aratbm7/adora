import os

from admin_auto_filters.filters import AutocompleteFilter
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from jalali_date.admin import ModelAdminJalaliMixin

from adora.models import *
from adora.tasks import (
    azkivam_cancel,
    azkivam_reverse,
    azkivam_status,
    azkivam_verify,
    send_order_status_message,
    snappay_cancel,
    snappay_revert,
    snappay_settle,
    snappay_status,
    snappay_verify,
    torobpay_cancel,
    torobpay_revert,
    torobpay_settle,
    torobpay_status,
    torobpay_verify,
)
from core.utils.separate_and_convert_to_fa import separate_digits_and_convert_to_fa
from core.utils.show_jalali_datetime import show_date_time

admin.site.site_header = "پنل ادمین آدورا یدک"
admin.site.site_title = "پنل ادمین آدورا یدک"
admin.site.index_title = " پنل ادمین آدورا یدک"

# admin.site.register(Matrial)
admin.site.register(OrderProvider)
admin.site.register(Banner)
# admin.site.register(Post)
# admin.site.register(PostImage)
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
        "id",
        "tracking_number",
        "view_items_link",
        "user_link",
        "profile_link",
        "payment_gateways",
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

    @admin.display(description="درگاه پرداخت")
    def payment_gateways(self, obj: Order):
        if obj.payment_reference == os.getenv("ZARIN_MERCHANT_NAME", "zarinpal"):
            return format_html(
                """
                <div style='
                    border-radius: 12px;
                    background: linear-gradient(135deg, #ffe082, #ffca28);
                    padding: 15px;
                    color: #333;
                    font-weight: bold;
                    text-align: center;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    margin: 10px 0;
                '>
                    درگاه پرداخت زرین پال
                </div>
                """
            )

        if obj.payment_reference == os.getenv("TOROBPAY_MERCHANT_NAME", "torobpay"):
            return self.torob_action_buttons(obj)

        if obj.payment_reference == os.getenv("AZKIVAM_MERHCHANT_NAME", "azkivam"):
            return self.azkivam_action_buttons(obj)

        if obj.payment_reference == os.getenv("SNAPPAY_MERHCHANT_NAME", "snappay"):
            return self.snap_action_buttons(obj)

    def snap_action_buttons(self, obj):
        style = """
            padding: 8px 4px !important;
            font-size: 11px !important;
            font-weight: bold !important;
            color: white !important;
            background-color: #008EFA !important;
            border: none !important;
            border-radius: 8px !important;
            cursor: pointer !important;
            transition: all 0.3s ease !important;
            width: 100% !important;
            min-height: 45px !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 2px !important;
            position: relative !important;
            box-shadow: 0 2px 8px rgba(0, 123, 255, 0.2) !important;
            text-align: center !important;
            line-height: 1.2 !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
        """

        hover = """
            this.style.setProperty('background-color', '#0056b3', 'important');
            this.style.setProperty('transform', 'translateY(-1px)', 'important');
            this.style.setProperty('box-shadow', '0 4px 12px rgba(0,123,255,0.3)', 'important');
        """

        reset_hover = """
            this.style.setProperty('background-color', '#008EFA', 'important');
            this.style.setProperty('transform', 'translateY(0px)', 'important');
            this.style.setProperty('box-shadow', '0 2px 4px rgba(0,0,0,0.1)', 'important');
        """

        # آیکن‌های ساده با SVG بدون استفاده از CDN یا فونت‌آوسم
        icons = {
            "status": mark_safe(
                """
                                <svg width="20" height="20" viewBox="0 0 21 13" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M19.77 1.78989C19.8443 1.72245 19.9044 1.64077 19.9466 1.5497C19.9888 1.45863 20.0123 1.36002 20.0157 1.2597C20.0191 1.15939 20.0023 1.05941 19.9663 0.965697C19.9304 0.871986 19.876 0.786445 19.8063 0.714144C19.7367 0.641843 19.6533 0.584253 19.561 0.544786C19.4687 0.505319 19.3694 0.484778 19.2691 0.484381C19.1687 0.483984 19.0693 0.503738 18.9767 0.542473C18.8841 0.581209 18.8002 0.638137 18.73 0.709885L11.98 7.20989C11.9057 7.27732 11.8456 7.359 11.8034 7.45007C11.7612 7.54114 11.7377 7.63975 11.7343 7.74007C11.7309 7.84039 11.7477 7.94036 11.7837 8.03407C11.8196 8.12779 11.874 8.21333 11.9437 8.28563C12.0133 8.35793 12.0967 8.41552 12.189 8.45499C12.2813 8.49445 12.3806 8.51499 12.4809 8.51539C12.5813 8.51579 12.6807 8.49603 12.7733 8.4573C12.8659 8.41856 12.9498 8.36163 13.02 8.28989L19.77 1.78989ZM16.987 0.999885H2.55C1.8737 0.999885 1.2251 1.26855 0.746878 1.74676C0.26866 2.22498 0 2.87358 0 3.54989V10.4499C0 10.7848 0.0659578 11.1163 0.194107 11.4257C0.322257 11.7351 0.510088 12.0162 0.746878 12.253C0.983667 12.4898 1.26478 12.6776 1.57416 12.8058C1.88354 12.9339 2.21513 12.9999 2.55 12.9999H17.45C17.7849 12.9999 18.1165 12.9339 18.4258 12.8058C18.7352 12.6776 19.0163 12.4898 19.2531 12.253C19.4899 12.0162 19.6777 11.7351 19.8059 11.4257C19.934 11.1163 20 10.7848 20 10.4499V3.54989C20 3.36455 19.981 3.18522 19.943 3.01189L13.713 9.01089C13.3786 9.33273 12.93 9.50853 12.4659 9.49962C12.0019 9.49071 11.5603 9.29782 11.2385 8.96339C10.9167 8.62895 10.7409 8.18036 10.7498 7.7163C10.7587 7.25224 10.9516 6.81073 11.286 6.48889L16.987 0.999885ZM2.5 5.24989C2.5 5.05097 2.57902 4.86021 2.71967 4.71956C2.86032 4.5789 3.05109 4.49989 3.25 4.49989H5.25C5.44891 4.49989 5.63968 4.5789 5.78033 4.71956C5.92098 4.86021 6 5.05097 6 5.24989C6 5.4488 5.92098 5.63956 5.78033 5.78021C5.63968 5.92087 5.44891 5.99989 5.25 5.99989H3.25C3.05109 5.99989 2.86032 5.92087 2.71967 5.78021C2.57902 5.63956 2.5 5.4488 2.5 5.24989ZM2.5 8.74989C2.5 8.55097 2.57902 8.36021 2.71967 8.21956C2.86032 8.0789 3.05109 7.99989 3.25 7.99989H8.25C8.44891 7.99989 8.63968 8.0789 8.78033 8.21956C8.92098 8.36021 9 8.55097 9 8.74989C9 8.9488 8.92098 9.13956 8.78033 9.28022C8.63968 9.42087 8.44891 9.49989 8.25 9.49989H3.25C3.05109 9.49989 2.86032 9.42087 2.71967 9.28022C2.57902 9.13956 2.5 8.9488 2.5 8.74989Z" fill="white"/>
                                </svg>
                                """
            ),
            "settle": mark_safe(
                """
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M4.44 12.076C4.24539 12.0117 4.0441 11.9698 3.84 11.951L3.699 11.945C2.761 11.945 2 12.728 2 13.693C2 14.567 2.623 15.291 3.437 15.421C3.465 15.4343 3.51067 15.4633 3.574 15.508C3.844 15.703 4.434 16.245 5.197 17.619C5.495 18.157 6.048 18.492 6.65 18.499C7.05794 18.5037 7.45349 18.3589 7.762 18.092M15 5.5C13.65 6.015 12.378 6.989 11.277 8.03C10.893 8.393 10.517 8.776 10.154 9.169M21.897 6.63C22.217 7.528 21.767 8.143 20.899 8.748C20.197 9.236 19.304 9.765 18.357 10.67C17.429 11.557 16.523 12.625 15.718 13.676C14.7332 14.9488 13.8281 16.2814 13.008 17.666C12.8629 17.921 12.6524 18.1328 12.3982 18.2793C12.1441 18.4259 11.8554 18.5021 11.562 18.5C11.2683 18.4937 10.9816 18.4095 10.7311 18.2561C10.4805 18.1028 10.2752 17.8857 10.136 17.627C9.388 16.264 8.81 15.726 8.544 15.533C7.807 14.996 7 14.903 7 13.733C7 12.776 7.746 12 8.667 12C9.325 12.027 9.929 12.309 10.456 12.693C10.798 12.942 11.161 13.271 11.538 13.705C11.98 13.051 12.513 12.297 13.111 11.516C13.979 10.383 15.003 9.166 16.101 8.117C17.181 7.085 18.431 6.119 19.754 5.609C20.617 5.276 21.576 5.732 21.897 6.63Z" stroke="#FFFBFB" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                </svg>
                                """
            ),
            "verify": mark_safe(
                """
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21.86 5.39192C22.288 6.49592 21.689 7.25192 20.53 7.99792C19.595 8.59792 18.404 9.24992 17.142 10.3629C15.904 11.4539 14.697 12.7689 13.624 14.0629C12.706 15.1738 11.832 16.3204 11.004 17.4999C10.59 18.0909 10.011 18.9729 10.011 18.9729C9.80322 19.2939 9.51707 19.5566 9.17956 19.7363C8.84205 19.916 8.46431 20.0067 8.082 19.9999C7.69991 19.9977 7.32474 19.8977 6.99218 19.7095C6.65962 19.5214 6.38072 19.2513 6.182 18.9249C5.183 17.2479 4.413 16.5849 4.059 16.3479C3.112 15.7099 2 15.6179 2 14.1339C2 12.9549 2.995 11.9999 4.222 11.9999C5.089 12.0319 5.894 12.3729 6.608 12.8529C7.064 13.1589 7.547 13.5649 8.049 14.0979C8.72176 13.1799 9.4214 12.2818 10.147 11.4049C11.304 10.0099 12.67 8.51292 14.135 7.22092C15.575 5.95092 17.24 4.76192 19.005 4.13392C20.155 3.72392 21.433 4.28692 21.86 5.39192Z" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                """
            ),
            "revert": mark_safe(
                """
                                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <g clip-path="url(#clip0_617_8402)">
                                <path d="M0.25 10C0.25 12.5859 1.27723 15.0658 3.10571 16.8943C4.93419 18.7228 7.41414 19.75 10 19.75C12.5859 19.75 15.0658 18.7228 16.8943 16.8943C18.7228 15.0658 19.75 12.5859 19.75 10C19.75 7.41414 18.7228 4.93419 16.8943 3.10571C15.0658 1.27723 12.5859 0.25 10 0.25C7.41414 0.25 4.93419 1.27723 3.10571 3.10571C1.27723 4.93419 0.25 7.41414 0.25 10Z" fill="#FF52A1" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M15.0406 12.7046C14.9606 12.3196 13.8856 11.1296 12.8006 9.99961C13.8856 8.86961 14.9606 7.67961 15.0406 7.29461C15.2706 6.84961 14.7256 6.23961 14.2456 5.75461C13.7656 5.26961 13.1506 4.75461 12.7056 4.95961C12.3206 5.03961 11.1306 6.11461 10.0006 7.19961C8.87059 6.11461 7.68059 5.03961 7.29559 4.95961C6.85059 4.72961 6.24059 5.27461 5.76059 5.75461C5.28059 6.23461 4.73059 6.84961 4.96059 7.29461C5.04059 7.67961 6.11558 8.86961 7.20058 9.99961C6.11558 11.1296 5.04059 12.3196 4.96059 12.7046C4.73059 13.1496 5.27559 13.7596 5.75559 14.2446C6.23559 14.7296 6.85059 15.2696 7.29559 15.0396C7.68059 14.9596 8.87059 13.8846 10.0006 12.7996C11.1306 13.8846 12.3206 14.9596 12.7056 15.0396C13.1506 15.2696 13.7606 14.7246 14.2456 14.2446C14.7306 13.7646 15.2706 13.1496 15.0406 12.7046Z" fill="white" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M13.7793 2.5C14.7778 2.92911 15.6741 3.5647 16.4093 4.365" stroke="white" stroke-width="0.5" stroke-miterlimit="10" stroke-linecap="round"/>
                                </g>
                                <defs>
                                <clipPath id="clip0_617_8402">
                                <rect width="30" height="30" fill="white"/>
                                </clipPath>
                                </defs>
                                </svg>
                                """
            ),
            "cancel": mark_safe(
                """
                                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <g clip-path="url(#clip0_617_8402)">
                                <path d="M0.25 10C0.25 12.5859 1.27723 15.0658 3.10571 16.8943C4.93419 18.7228 7.41414 19.75 10 19.75C12.5859 19.75 15.0658 18.7228 16.8943 16.8943C18.7228 15.0658 19.75 12.5859 19.75 10C19.75 7.41414 18.7228 4.93419 16.8943 3.10571C15.0658 1.27723 12.5859 0.25 10 0.25C7.41414 0.25 4.93419 1.27723 3.10571 3.10571C1.27723 4.93419 0.25 7.41414 0.25 10Z" fill="#E80101" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M15.0406 12.7046C14.9606 12.3196 13.8856 11.1296 12.8006 9.99961C13.8856 8.86961 14.9606 7.67961 15.0406 7.29461C15.2706 6.84961 14.7256 6.23961 14.2456 5.75461C13.7656 5.26961 13.1506 4.75461 12.7056 4.95961C12.3206 5.03961 11.1306 6.11461 10.0006 7.19961C8.87059 6.11461 7.68059 5.03961 7.29559 4.95961C6.85059 4.72961 6.24059 5.27461 5.76059 5.75461C5.28059 6.23461 4.73059 6.84961 4.96059 7.29461C5.04059 7.67961 6.11558 8.86961 7.20058 9.99961C6.11558 11.1296 5.04059 12.3196 4.96059 12.7046C4.73059 13.1496 5.27559 13.7596 5.75559 14.2446C6.23559 14.7296 6.85059 15.2696 7.29559 15.0396C7.68059 14.9596 8.87059 13.8846 10.0006 12.7996C11.1306 13.8846 12.3206 14.9596 12.7056 15.0396C13.1506 15.2696 13.7606 14.7246 14.2456 14.2446C14.7306 13.7646 15.2706 13.1496 15.0406 12.7046Z" fill="white" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M13.7793 2.5C14.7778 2.92911 15.6741 3.5647 16.4093 4.365" stroke="white" stroke-width="0.5" stroke-miterlimit="10" stroke-linecap="round"/>
                                </g>
                                <defs>
                                <clipPath id="clip0_617_8402">
                                <rect width="30" height="30" fill="white"/>
                                </clipPath>
                                </defs>
                                </svg>
                                """
            ),
        }

        # تول‌تیپ‌ها (خلاصه توضیحات مستندات)
        tooltips = {
            "status": """بررسی مرحله فعلی پرداخت (تراکنش ایجاد شده، وریفای شده یا تسویه‌شده)

                STATUS API OUTPUT:

                    PENDING => NEW, IPG, W_FOR_VERIFY
                    VERIFY =>  W_FOR_SETTLE
                    SETTLE => ONGOING, PAID, UPDATED
                    REVERT => CANCELED ,FAILED , ...
                                            """,
            "verify": "(Verify) بررسی اعتبار توکن پرداخت ترب (برای اطمینان از صحت پرداخت)",
            "settle": "(Settle) تأیید نهایی پرداخت و تغییر وضعیت به ongoing",
            "revert": "(Revert)",
            "cancel": "(Cancel) لغو کامل سفارش و بازگشت مبلغ پرداخت شده در صورت نیاز",
        }

        # متن‌های دکمه‌ها
        button_texts = {
            "status": "وضعیت",
            "verify": "تأیید",
            "settle": "نهایی",
            "revert": "بازگشت",
            "cancel": "لغو",
        }

        return format_html(
            """
            <style>
                .torob-box {{
                    border: 1px solid #008EFA !important;
                    background-color: #f6fff8 !important;
                    padding: 15px !important;
                    border-radius: 12px !important;
                    margin: 5px 0 !important;
                    box-shadow: 0 2px 6px rgba(0, 128, 0, 0.1) !important;
                    position: relative !important;
                    width: 100% !important;
                    box-sizing: border-box !important;
                }}

                .torob-label {{
                    display: inline-block !important;
                    background-color: #0000b8 !important;
                    color: white !important;
                    padding: 4px 10px !important;
                    border-radius: 20px !important;
                    font-size: 11px !important;
                    font-weight: bold !important;
                    position: absolute !important;
                    top: -8px !important;
                    right: 10px !important;
                    z-index: 1000 !important;
                }}

                .torob-buttons {{
                    display: grid !important;
                    grid-template-columns: repeat(5, 1fr) !important;
                    gap: 6px !important;
                    margin-top: 8px !important;
                    width: 100% !important;
                }}

                .torob-buttons button:active {{
                    transform: translateY(1px) !important;
                    box-shadow: 0 1px 4px rgba(0, 123, 255, 0.3) !important;
                }}

                /* تبلت - نمایش 3 ستونه */
                @media screen and (max-width: 768px) and (min-width: 481px) {{
                    .torob-buttons {{
                        grid-template-columns: repeat(3, 1fr) !important;
                        gap: 8px !important;
                    }}
                    .torob-buttons button {{
                        min-height: 50px !important;
                        font-size: 12px !important;
                    }}
                }}

                /* موبایل بزرگ - نمایش 2 ستونه */
                @media screen and (max-width: 480px) and (min-width: 361px) {{
                    .torob-box {{
                        padding: 12px !important;
                    }}
                    .torob-buttons {{
                        grid-template-columns: repeat(2, 1fr) !important;
                        gap: 6px !important;
                    }}
                    .torob-buttons button {{
                        min-height: 55px !important;
                        font-size: 10px !important;
                        padding: 6px 4px !important;
                    }}
                    .torob-label {{
                        font-size: 10px !important;
                        padding: 3px 8px !important;
                        top: -6px !important;
                    }}
                }}

                /* موبایل کوچک */
                @media screen and (max-width: 360px) {{
                    .torob-box {{
                        padding: 10px !important;
                    }}
                    .torob-buttons {{
                        grid-template-columns: repeat(2, 1fr) !important;
                        gap: 4px !important;
                    }}
                    .torob-buttons button {{
                        min-height: 50px !important;
                        font-size: 9px !important;
                        padding: 4px 2px !important;
                    }}
                    .torob-label {{
                        font-size: 9px !important;
                        padding: 2px 6px !important;
                        top: -5px !important;
                    }}
                }}
            </style>


            <div class="torob-box">
                <div class="torob-label">درگاه پرداخت  اسنپ  پی</div>
                <div class="torob-buttons">
                    <button type="button" class="snap-check" data-id="{0}" data-action="status"
                        title="{1}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {5}
                        <span>{13}</span>
                    </button>
                    <button type="button" class="snap-check" data-id="{0}" data-action="verify"
                        title="{6}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {7}
                        <span>{14}</span>
                    </button>
                    <button type="button" class="snap-check" data-id="{0}" data-action="settle"
                        title="{8}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {9}
                        <span>{15}</span>
                    </button>
                    <button type="button" class="snap-check" data-id="{0}" data-action="revert"
                        title="{10}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {11}
                        <span>{16}</span>
                    </button>
                    <button type="button" class="snap-check" data-id="{0}" data-action="cancel"
                        title="{12}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {17}
                        <span>{18}</span>
                    </button>
                </div>
            </div>
            """,
            obj.id,  # 0
            tooltips["status"],  # 1
            style.strip(),  # 2
            hover.strip(),  # 3
            reset_hover.strip(),  # 4
            icons["status"],  # 5
            tooltips["verify"],  # 6
            icons["verify"],  # 7
            tooltips["settle"],  # 8
            icons["settle"],  # 9
            tooltips["revert"],  # 10
            icons["revert"],  # 11
            tooltips["cancel"],  # 12
            button_texts["status"],  # 13
            button_texts["verify"],  # 14
            button_texts["settle"],  # 15
            button_texts["revert"],  # 16
            icons["cancel"],  # 17
            button_texts["cancel"],  # 18
        )

    def torob_action_buttons(self, obj):
        style = """
            padding: 8px 4px !important;
            font-size: 11px !important;
            font-weight: bold !important;
            color: white !important;
            background-color: #007bff !important;
            border: none !important;
            border-radius: 8px !important;
            cursor: pointer !important;
            transition: all 0.3s ease !important;
            width: 100% !important;
            min-height: 45px !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 2px !important;
            position: relative !important;
            box-shadow: 0 2px 8px rgba(0, 123, 255, 0.2) !important;
            text-align: center !important;
            line-height: 1.2 !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
        """

        hover = """
            this.style.setProperty('background-color', '#0056b3', 'important');
            this.style.setProperty('transform', 'translateY(-1px)', 'important');
            this.style.setProperty('box-shadow', '0 4px 12px rgba(0,123,255,0.3)', 'important');
        """

        reset_hover = """
            this.style.setProperty('background-color', '#007bff', 'important');
            this.style.setProperty('transform', 'translateY(0px)', 'important');
            this.style.setProperty('box-shadow', '0 2px 4px rgba(0,0,0,0.1)', 'important');
        """

        # آیکن‌های ساده با SVG بدون استفاده از CDN یا فونت‌آوسم
        icons = {
            "status": mark_safe(
                """
                                <svg width="20" height="20" viewBox="0 0 21 13" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M19.77 1.78989C19.8443 1.72245 19.9044 1.64077 19.9466 1.5497C19.9888 1.45863 20.0123 1.36002 20.0157 1.2597C20.0191 1.15939 20.0023 1.05941 19.9663 0.965697C19.9304 0.871986 19.876 0.786445 19.8063 0.714144C19.7367 0.641843 19.6533 0.584253 19.561 0.544786C19.4687 0.505319 19.3694 0.484778 19.2691 0.484381C19.1687 0.483984 19.0693 0.503738 18.9767 0.542473C18.8841 0.581209 18.8002 0.638137 18.73 0.709885L11.98 7.20989C11.9057 7.27732 11.8456 7.359 11.8034 7.45007C11.7612 7.54114 11.7377 7.63975 11.7343 7.74007C11.7309 7.84039 11.7477 7.94036 11.7837 8.03407C11.8196 8.12779 11.874 8.21333 11.9437 8.28563C12.0133 8.35793 12.0967 8.41552 12.189 8.45499C12.2813 8.49445 12.3806 8.51499 12.4809 8.51539C12.5813 8.51579 12.6807 8.49603 12.7733 8.4573C12.8659 8.41856 12.9498 8.36163 13.02 8.28989L19.77 1.78989ZM16.987 0.999885H2.55C1.8737 0.999885 1.2251 1.26855 0.746878 1.74676C0.26866 2.22498 0 2.87358 0 3.54989V10.4499C0 10.7848 0.0659578 11.1163 0.194107 11.4257C0.322257 11.7351 0.510088 12.0162 0.746878 12.253C0.983667 12.4898 1.26478 12.6776 1.57416 12.8058C1.88354 12.9339 2.21513 12.9999 2.55 12.9999H17.45C17.7849 12.9999 18.1165 12.9339 18.4258 12.8058C18.7352 12.6776 19.0163 12.4898 19.2531 12.253C19.4899 12.0162 19.6777 11.7351 19.8059 11.4257C19.934 11.1163 20 10.7848 20 10.4499V3.54989C20 3.36455 19.981 3.18522 19.943 3.01189L13.713 9.01089C13.3786 9.33273 12.93 9.50853 12.4659 9.49962C12.0019 9.49071 11.5603 9.29782 11.2385 8.96339C10.9167 8.62895 10.7409 8.18036 10.7498 7.7163C10.7587 7.25224 10.9516 6.81073 11.286 6.48889L16.987 0.999885ZM2.5 5.24989C2.5 5.05097 2.57902 4.86021 2.71967 4.71956C2.86032 4.5789 3.05109 4.49989 3.25 4.49989H5.25C5.44891 4.49989 5.63968 4.5789 5.78033 4.71956C5.92098 4.86021 6 5.05097 6 5.24989C6 5.4488 5.92098 5.63956 5.78033 5.78021C5.63968 5.92087 5.44891 5.99989 5.25 5.99989H3.25C3.05109 5.99989 2.86032 5.92087 2.71967 5.78021C2.57902 5.63956 2.5 5.4488 2.5 5.24989ZM2.5 8.74989C2.5 8.55097 2.57902 8.36021 2.71967 8.21956C2.86032 8.0789 3.05109 7.99989 3.25 7.99989H8.25C8.44891 7.99989 8.63968 8.0789 8.78033 8.21956C8.92098 8.36021 9 8.55097 9 8.74989C9 8.9488 8.92098 9.13956 8.78033 9.28022C8.63968 9.42087 8.44891 9.49989 8.25 9.49989H3.25C3.05109 9.49989 2.86032 9.42087 2.71967 9.28022C2.57902 9.13956 2.5 8.9488 2.5 8.74989Z" fill="white"/>
                                </svg>
                                """
            ),
            "settle": mark_safe(
                """
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M4.44 12.076C4.24539 12.0117 4.0441 11.9698 3.84 11.951L3.699 11.945C2.761 11.945 2 12.728 2 13.693C2 14.567 2.623 15.291 3.437 15.421C3.465 15.4343 3.51067 15.4633 3.574 15.508C3.844 15.703 4.434 16.245 5.197 17.619C5.495 18.157 6.048 18.492 6.65 18.499C7.05794 18.5037 7.45349 18.3589 7.762 18.092M15 5.5C13.65 6.015 12.378 6.989 11.277 8.03C10.893 8.393 10.517 8.776 10.154 9.169M21.897 6.63C22.217 7.528 21.767 8.143 20.899 8.748C20.197 9.236 19.304 9.765 18.357 10.67C17.429 11.557 16.523 12.625 15.718 13.676C14.7332 14.9488 13.8281 16.2814 13.008 17.666C12.8629 17.921 12.6524 18.1328 12.3982 18.2793C12.1441 18.4259 11.8554 18.5021 11.562 18.5C11.2683 18.4937 10.9816 18.4095 10.7311 18.2561C10.4805 18.1028 10.2752 17.8857 10.136 17.627C9.388 16.264 8.81 15.726 8.544 15.533C7.807 14.996 7 14.903 7 13.733C7 12.776 7.746 12 8.667 12C9.325 12.027 9.929 12.309 10.456 12.693C10.798 12.942 11.161 13.271 11.538 13.705C11.98 13.051 12.513 12.297 13.111 11.516C13.979 10.383 15.003 9.166 16.101 8.117C17.181 7.085 18.431 6.119 19.754 5.609C20.617 5.276 21.576 5.732 21.897 6.63Z" stroke="#FFFBFB" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                </svg>
                                """
            ),
            "verify": mark_safe(
                """
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21.86 5.39192C22.288 6.49592 21.689 7.25192 20.53 7.99792C19.595 8.59792 18.404 9.24992 17.142 10.3629C15.904 11.4539 14.697 12.7689 13.624 14.0629C12.706 15.1738 11.832 16.3204 11.004 17.4999C10.59 18.0909 10.011 18.9729 10.011 18.9729C9.80322 19.2939 9.51707 19.5566 9.17956 19.7363C8.84205 19.916 8.46431 20.0067 8.082 19.9999C7.69991 19.9977 7.32474 19.8977 6.99218 19.7095C6.65962 19.5214 6.38072 19.2513 6.182 18.9249C5.183 17.2479 4.413 16.5849 4.059 16.3479C3.112 15.7099 2 15.6179 2 14.1339C2 12.9549 2.995 11.9999 4.222 11.9999C5.089 12.0319 5.894 12.3729 6.608 12.8529C7.064 13.1589 7.547 13.5649 8.049 14.0979C8.72176 13.1799 9.4214 12.2818 10.147 11.4049C11.304 10.0099 12.67 8.51292 14.135 7.22092C15.575 5.95092 17.24 4.76192 19.005 4.13392C20.155 3.72392 21.433 4.28692 21.86 5.39192Z" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                """
            ),
            "revert": mark_safe(
                """
                                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <g clip-path="url(#clip0_617_8402)">
                                <path d="M0.25 10C0.25 12.5859 1.27723 15.0658 3.10571 16.8943C4.93419 18.7228 7.41414 19.75 10 19.75C12.5859 19.75 15.0658 18.7228 16.8943 16.8943C18.7228 15.0658 19.75 12.5859 19.75 10C19.75 7.41414 18.7228 4.93419 16.8943 3.10571C15.0658 1.27723 12.5859 0.25 10 0.25C7.41414 0.25 4.93419 1.27723 3.10571 3.10571C1.27723 4.93419 0.25 7.41414 0.25 10Z" fill="#FF52A1" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M15.0406 12.7046C14.9606 12.3196 13.8856 11.1296 12.8006 9.99961C13.8856 8.86961 14.9606 7.67961 15.0406 7.29461C15.2706 6.84961 14.7256 6.23961 14.2456 5.75461C13.7656 5.26961 13.1506 4.75461 12.7056 4.95961C12.3206 5.03961 11.1306 6.11461 10.0006 7.19961C8.87059 6.11461 7.68059 5.03961 7.29559 4.95961C6.85059 4.72961 6.24059 5.27461 5.76059 5.75461C5.28059 6.23461 4.73059 6.84961 4.96059 7.29461C5.04059 7.67961 6.11558 8.86961 7.20058 9.99961C6.11558 11.1296 5.04059 12.3196 4.96059 12.7046C4.73059 13.1496 5.27559 13.7596 5.75559 14.2446C6.23559 14.7296 6.85059 15.2696 7.29559 15.0396C7.68059 14.9596 8.87059 13.8846 10.0006 12.7996C11.1306 13.8846 12.3206 14.9596 12.7056 15.0396C13.1506 15.2696 13.7606 14.7246 14.2456 14.2446C14.7306 13.7646 15.2706 13.1496 15.0406 12.7046Z" fill="white" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M13.7793 2.5C14.7778 2.92911 15.6741 3.5647 16.4093 4.365" stroke="white" stroke-width="0.5" stroke-miterlimit="10" stroke-linecap="round"/>
                                </g>
                                <defs>
                                <clipPath id="clip0_617_8402">
                                <rect width="30" height="30" fill="white"/>
                                </clipPath>
                                </defs>
                                </svg>
                                """
            ),
            "cancel": mark_safe(
                """
                                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <g clip-path="url(#clip0_617_8402)">
                                <path d="M0.25 10C0.25 12.5859 1.27723 15.0658 3.10571 16.8943C4.93419 18.7228 7.41414 19.75 10 19.75C12.5859 19.75 15.0658 18.7228 16.8943 16.8943C18.7228 15.0658 19.75 12.5859 19.75 10C19.75 7.41414 18.7228 4.93419 16.8943 3.10571C15.0658 1.27723 12.5859 0.25 10 0.25C7.41414 0.25 4.93419 1.27723 3.10571 3.10571C1.27723 4.93419 0.25 7.41414 0.25 10Z" fill="#E80101" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M15.0406 12.7046C14.9606 12.3196 13.8856 11.1296 12.8006 9.99961C13.8856 8.86961 14.9606 7.67961 15.0406 7.29461C15.2706 6.84961 14.7256 6.23961 14.2456 5.75461C13.7656 5.26961 13.1506 4.75461 12.7056 4.95961C12.3206 5.03961 11.1306 6.11461 10.0006 7.19961C8.87059 6.11461 7.68059 5.03961 7.29559 4.95961C6.85059 4.72961 6.24059 5.27461 5.76059 5.75461C5.28059 6.23461 4.73059 6.84961 4.96059 7.29461C5.04059 7.67961 6.11558 8.86961 7.20058 9.99961C6.11558 11.1296 5.04059 12.3196 4.96059 12.7046C4.73059 13.1496 5.27559 13.7596 5.75559 14.2446C6.23559 14.7296 6.85059 15.2696 7.29559 15.0396C7.68059 14.9596 8.87059 13.8846 10.0006 12.7996C11.1306 13.8846 12.3206 14.9596 12.7056 15.0396C13.1506 15.2696 13.7606 14.7246 14.2456 14.2446C14.7306 13.7646 15.2706 13.1496 15.0406 12.7046Z" fill="white" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M13.7793 2.5C14.7778 2.92911 15.6741 3.5647 16.4093 4.365" stroke="white" stroke-width="0.5" stroke-miterlimit="10" stroke-linecap="round"/>
                                </g>
                                <defs>
                                <clipPath id="clip0_617_8402">
                                <rect width="30" height="30" fill="white"/>
                                </clipPath>
                                </defs>
                                </svg>
                                """
            ),
        }

        # تول‌تیپ‌ها (خلاصه توضیحات مستندات)
        tooltips = {
            "status": """بررسی مرحله فعلی پرداخت (تراکنش ایجاد شده، وریفای شده یا تسویه‌شده)

                STATUS API OUTPUT:

                    PENDING => NEW, IPG, W_FOR_VERIFY
                    VERIFY =>  W_FOR_SETTLE
                    SETTLE => ONGOING, PAID, UPDATED
                    REVERT => CANCELED ,FAILED , ...
                                            """,
            "verify": "(Verify) بررسی اعتبار توکن پرداخت ترب (برای اطمینان از صحت پرداخت)",
            "settle": "(Settle) تأیید نهایی پرداخت و تغییر وضعیت به ongoing",
            "revert": "(Revert) بازگشت وجه تا ۳۰ دقیقه بعد از پرداخت در صورت نهایی نشدن",
            "cancel": "(Cancel) لغو کامل سفارش و بازگشت مبلغ پرداخت شده در صورت نیاز",
        }

        # متن‌های دکمه‌ها
        button_texts = {
            "status": "وضعیت",
            "verify": "تأیید",
            "settle": "نهایی",
            "revert": "بازگشت",
            "cancel": "لغو",
        }

        return format_html(
            """
            <style>
                .torob-box {{
                    border: 1px solid #d0f0c0 !important;
                    background-color: #f6fff8 !important;
                    padding: 15px !important;
                    border-radius: 12px !important;
                    margin: 5px 0 !important;
                    box-shadow: 0 2px 6px rgba(0, 128, 0, 0.1) !important;
                    position: relative !important;
                    width: 100% !important;
                    box-sizing: border-box !important;
                }}

                .torob-label {{
                    display: inline-block !important;
                    background-color: #4caf50 !important;
                    color: white !important;
                    padding: 4px 10px !important;
                    border-radius: 20px !important;
                    font-size: 11px !important;
                    font-weight: bold !important;
                    position: absolute !important;
                    top: -8px !important;
                    right: 10px !important;
                    z-index: 1000 !important;
                }}

                .torob-buttons {{
                    display: grid !important;
                    grid-template-columns: repeat(5, 1fr) !important;
                    gap: 6px !important;
                    margin-top: 8px !important;
                    width: 100% !important;
                }}

                .torob-buttons button:active {{
                    transform: translateY(1px) !important;
                    box-shadow: 0 1px 4px rgba(0, 123, 255, 0.3) !important;
                }}

                /* تبلت - نمایش 3 ستونه */
                @media screen and (max-width: 768px) and (min-width: 481px) {{
                    .torob-buttons {{
                        grid-template-columns: repeat(3, 1fr) !important;
                        gap: 8px !important;
                    }}
                    .torob-buttons button {{
                        min-height: 50px !important;
                        font-size: 12px !important;
                    }}
                }}

                /* موبایل بزرگ - نمایش 2 ستونه */
                @media screen and (max-width: 480px) and (min-width: 361px) {{
                    .torob-box {{
                        padding: 12px !important;
                    }}
                    .torob-buttons {{
                        grid-template-columns: repeat(2, 1fr) !important;
                        gap: 6px !important;
                    }}
                    .torob-buttons button {{
                        min-height: 55px !important;
                        font-size: 10px !important;
                        padding: 6px 4px !important;
                    }}
                    .torob-label {{
                        font-size: 10px !important;
                        padding: 3px 8px !important;
                        top: -6px !important;
                    }}
                }}

                /* موبایل کوچک */
                @media screen and (max-width: 360px) {{
                    .torob-box {{
                        padding: 10px !important;
                    }}
                    .torob-buttons {{
                        grid-template-columns: repeat(2, 1fr) !important;
                        gap: 4px !important;
                    }}
                    .torob-buttons button {{
                        min-height: 50px !important;
                        font-size: 9px !important;
                        padding: 4px 2px !important;
                    }}
                    .torob-label {{
                        font-size: 9px !important;
                        padding: 2px 6px !important;
                        top: -5px !important;
                    }}
                }}
            </style>


            <div class="torob-box">
                <div class="torob-label">درگاه پرداخت ترب پی</div>
                <div class="torob-buttons">
                    <button type="button" class="torob-check" data-id="{0}" data-action="status"
                        title="{1}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {5}
                        <span>{13}</span>
                    </button>
                    <button type="button" class="torob-check" data-id="{0}" data-action="verify"
                        title="{6}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {7}
                        <span>{14}</span>
                    </button>
                    <button type="button" class="torob-check" data-id="{0}" data-action="settle"
                        title="{8}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {9}
                        <span>{15}</span>
                    </button>
                    <button type="button" class="torob-check" data-id="{0}" data-action="revert"
                        title="{10}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {11}
                        <span>{16}</span>
                    </button>
                    <button type="button" class="torob-check" data-id="{0}" data-action="cancel"
                        title="{12}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {17}
                        <span>{18}</span>
                    </button>
                </div>
            </div>
            """,
            obj.id,  # 0
            tooltips["status"],  # 1
            style.strip(),  # 2
            hover.strip(),  # 3
            reset_hover.strip(),  # 4
            icons["status"],  # 5
            tooltips["verify"],  # 6
            icons["verify"],  # 7
            tooltips["settle"],  # 8
            icons["settle"],  # 9
            tooltips["revert"],  # 10
            icons["revert"],  # 11
            tooltips["cancel"],  # 12
            button_texts["status"],  # 13
            button_texts["verify"],  # 14
            button_texts["settle"],  # 15
            button_texts["revert"],  # 16
            icons["cancel"],  # 17
            button_texts["cancel"],  # 18
        )

    def azkivam_action_buttons(self, obj):
        style = """
            padding: 8px 4px !important;
            font-size: 11px !important;
            font-weight: bold !important;
            color: white !important;
            background-color: #1a1a2e !important;
            border: none !important;
            border-radius: 8px !important;
            cursor: pointer !important;
            transition: all 0.3s ease !important;
            width: 100% !important;
            min-height: 45px !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 2px !important;
            position: relative !important;
            box-shadow: 0 2px 8px rgba(26, 26, 46, 0.3) !important;
            text-align: center !important;
            line-height: 1.2 !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
        """

        hover = """
            this.style.setProperty('backgroud-color', 'linear-gradient(135deg, #0f3460, #16213e)', 'important');
            this.style.setProperty('transform', 'translateY(-1px)', 'important');
            this.style.setProperty('box-shadow', '0 4px 12px rgba(15, 52, 96, 0.4)', 'important');
        """

        reset_hover = """
            this.style.setProperty('background-color', '#6C63FF', important');
            this.style.setProperty('transform', 'translateY(0px)', 'important');
            this.style.setProperty('box-shadow', '0 2px 4px rgba(0,0,0,0.1)', 'important');
        """

        # آیکن‌های ساده با SVG بدون استفاده از CDN یا فونت‌آوسم
        icons = {
            "status": mark_safe(
                """
                                <svg width="20" height="20" viewBox="0 0 21 13" fill="#00d4aa" xmlns="http://www.w3.org/2000/svg">
                                <path d="M19.77 1.78989C19.8443 1.72245 19.9044 1.64077 19.9466 1.5497C19.9888 1.45863 20.0123 1.36002 20.0157 1.2597C20.0191 1.15939 20.0023 1.05941 19.9663 0.965697C19.9304 0.871986 19.876 0.786445 19.8063 0.714144C19.7367 0.641843 19.6533 0.584253 19.561 0.544786C19.4687 0.505319 19.3694 0.484778 19.2691 0.484381C19.1687 0.483984 19.0693 0.503738 18.9767 0.542473C18.8841 0.581209 18.8002 0.638137 18.73 0.709885L11.98 7.20989C11.9057 7.27732 11.8456 7.359 11.8034 7.45007C11.7612 7.54114 11.7377 7.63975 11.7343 7.74007C11.7309 7.84039 11.7477 7.94036 11.7837 8.03407C11.8196 8.12779 11.874 8.21333 11.9437 8.28563C12.0133 8.35793 12.0967 8.41552 12.189 8.45499C12.2813 8.49445 12.3806 8.51499 12.4809 8.51539C12.5813 8.51579 12.6807 8.49603 12.7733 8.4573C12.8659 8.41856 12.9498 8.36163 13.02 8.28989L19.77 1.78989ZM16.987 0.999885H2.55C1.8737 0.999885 1.2251 1.26855 0.746878 1.74676C0.26866 2.22498 0 2.87358 0 3.54989V10.4499C0 10.7848 0.0659578 11.1163 0.194107 11.4257C0.322257 11.7351 0.510088 12.0162 0.746878 12.253C0.983667 12.4898 1.26478 12.6776 1.57416 12.8058C1.88354 12.9339 2.21513 12.9999 2.55 12.9999H17.45C17.7849 12.9999 18.1165 12.9339 18.4258 12.8058C18.7352 12.6776 19.0163 12.4898 19.2531 12.253C19.4899 12.0162 19.6777 11.7351 19.8059 11.4257C19.934 11.1163 20 10.7848 20 10.4499V3.54989C20 3.36455 19.981 3.18522 19.943 3.01189L13.713 9.01089C13.3786 9.33273 12.93 9.50853 12.4659 9.49962C12.0019 9.49071 11.5603 9.29782 11.2385 8.96339C10.9167 8.62895 10.7409 8.18036 10.7498 7.7163C10.7587 7.25224 10.9516 6.81073 11.286 6.48889L16.987 0.999885ZM2.5 5.24989C2.5 5.05097 2.57902 4.86021 2.71967 4.71956C2.86032 4.5789 3.05109 4.49989 3.25 4.49989H5.25C5.44891 4.49989 5.63968 4.5789 5.78033 4.71956C5.92098 4.86021 6 5.05097 6 5.24989C6 5.4488 5.92098 5.63956 5.78033 5.78021C5.63968 5.92087 5.44891 5.99989 5.25 5.99989H3.25C3.05109 5.99989 2.86032 5.92087 2.71967 5.78021C2.57902 5.63956 2.5 5.4488 2.5 5.24989ZM2.5 8.74989C2.5 8.55097 2.57902 8.36021 2.71967 8.21956C2.86032 8.0789 3.05109 7.99989 3.25 7.99989H8.25C8.44891 7.99989 8.63968 8.0789 8.78033 8.21956C8.92098 8.36021 9 8.55097 9 8.74989C9 8.9488 8.92098 9.13956 8.78033 9.28022C8.63968 9.42087 8.44891 9.49989 8.25 9.49989H3.25C3.05109 9.49989 2.86032 9.42087 2.71967 9.28022C2.57902 9.13956 2.5 8.9488 2.5 8.74989Z" fill="white"/>
                                </svg>
                                """
            ),
            "verify": mark_safe(
                """
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21.86 5.39192C22.288 6.49592 21.689 7.25192 20.53 7.99792C19.595 8.59792 18.404 9.24992 17.142 10.3629C15.904 11.4539 14.697 12.7689 13.624 14.0629C12.706 15.1738 11.832 16.3204 11.004 17.4999C10.59 18.0909 10.011 18.9729 10.011 18.9729C9.80322 19.2939 9.51707 19.5566 9.17956 19.7363C8.84205 19.916 8.46431 20.0067 8.082 19.9999C7.69991 19.9977 7.32474 19.8977 6.99218 19.7095C6.65962 19.5214 6.38072 19.2513 6.182 18.9249C5.183 17.2479 4.413 16.5849 4.059 16.3479C3.112 15.7099 2 15.6179 2 14.1339C2 12.9549 2.995 11.9999 4.222 11.9999C5.089 12.0319 5.894 12.3729 6.608 12.8529C7.064 13.1589 7.547 13.5649 8.049 14.0979C8.72176 13.1799 9.4214 12.2818 10.147 11.4049C11.304 10.0099 12.67 8.51292 14.135 7.22092C15.575 5.95092 17.24 4.76192 19.005 4.13392C20.155 3.72392 21.433 4.28692 21.86 5.39192Z" stroke="#ff6b6b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                """
            ),
            "revers": mark_safe(
                """
                                <svg width="18" height="18" viewBox="0 0 20 20" fill="#ff6b6b" xmlns="http://www.w3.org/2000/svg">
                                <g clip-path="url(#clip0_617_8402)">
                                <path d="M0.25 10C0.25 12.5859 1.27723 15.0658 3.10571 16.8943C4.93419 18.7228 7.41414 19.75 10 19.75C12.5859 19.75 15.0658 18.7228 16.8943 16.8943C18.7228 15.0658 19.75 12.5859 19.75 10C19.75 7.41414 18.7228 4.93419 16.8943 3.10571C15.0658 1.27723 12.5859 0.25 10 0.25C7.41414 0.25 4.93419 1.27723 3.10571 3.10571C1.27723 4.93419 0.25 7.41414 0.25 10Z" fill="#FF52A1" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M15.0406 12.7046C14.9606 12.3196 13.8856 11.1296 12.8006 9.99961C13.8856 8.86961 14.9606 7.67961 15.0406 7.29461C15.2706 6.84961 14.7256 6.23961 14.2456 5.75461C13.7656 5.26961 13.1506 4.75461 12.7056 4.95961C12.3206 5.03961 11.1306 6.11461 10.0006 7.19961C8.87059 6.11461 7.68059 5.03961 7.29559 4.95961C6.85059 4.72961 6.24059 5.27461 5.76059 5.75461C5.28059 6.23461 4.73059 6.84961 4.96059 7.29461C5.04059 7.67961 6.11558 8.86961 7.20058 9.99961C6.11558 11.1296 5.04059 12.3196 4.96059 12.7046C4.73059 13.1496 5.27559 13.7596 5.75559 14.2446C6.23559 14.7296 6.85059 15.2696 7.29559 15.0396C7.68059 14.9596 8.87059 13.8846 10.0006 12.7996C11.1306 13.8846 12.3206 14.9596 12.7056 15.0396C13.1506 15.2696 13.7606 14.7246 14.2456 14.2446C14.7306 13.7646 15.2706 13.1496 15.0406 12.7046Z" fill="white" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M13.7793 2.5C14.7778 2.92911 15.6741 3.5647 16.4093 4.365" stroke="white" stroke-width="0.5" stroke-miterlimit="10" stroke-linecap="round"/>
                                </g>
                                <defs>
                                <clipPath id="clip0_617_8402">
                                <rect width="30" height="30" fill="white"/>
                                </clipPath>
                                </defs>
                                </svg>
                                """
            ),
            "cancel": mark_safe(
                """
                                <svg width="18" height="18" viewBox="0 0 20 20" fil="#ff4757" xmlns="http://www.w3.org/2000/svg">
                                <g clip-path="url(#clip0_617_8402)">
                                <path d="M0.25 10C0.25 12.5859 1.27723 15.0658 3.10571 16.8943C4.93419 18.7228 7.41414 19.75 10 19.75C12.5859 19.75 15.0658 18.7228 16.8943 16.8943C18.7228 15.0658 19.75 12.5859 19.75 10C19.75 7.41414 18.7228 4.93419 16.8943 3.10571C15.0658 1.27723 12.5859 0.25 10 0.25C7.41414 0.25 4.93419 1.27723 3.10571 3.10571C1.27723 4.93419 0.25 7.41414 0.25 10Z" fill="#E80101" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M15.0406 12.7046C14.9606 12.3196 13.8856 11.1296 12.8006 9.99961C13.8856 8.86961 14.9606 7.67961 15.0406 7.29461C15.2706 6.84961 14.7256 6.23961 14.2456 5.75461C13.7656 5.26961 13.1506 4.75461 12.7056 4.95961C12.3206 5.03961 11.1306 6.11461 10.0006 7.19961C8.87059 6.11461 7.68059 5.03961 7.29559 4.95961C6.85059 4.72961 6.24059 5.27461 5.76059 5.75461C5.28059 6.23461 4.73059 6.84961 4.96059 7.29461C5.04059 7.67961 6.11558 8.86961 7.20058 9.99961C6.11558 11.1296 5.04059 12.3196 4.96059 12.7046C4.73059 13.1496 5.27559 13.7596 5.75559 14.2446C6.23559 14.7296 6.85059 15.2696 7.29559 15.0396C7.68059 14.9596 8.87059 13.8846 10.0006 12.7996C11.1306 13.8846 12.3206 14.9596 12.7056 15.0396C13.1506 15.2696 13.7606 14.7246 14.2456 14.2446C14.7306 13.7646 15.2706 13.1496 15.0406 12.7046Z" fill="white" stroke="#231F20" stroke-width="0.5" stroke-miterlimit="10"/>
                                <path d="M13.7793 2.5C14.7778 2.92911 15.6741 3.5647 16.4093 4.365" stroke="white" stroke-width="0.5" stroke-miterlimit="10" stroke-linecap="round"/>
                                </g>
                                <defs>
                                <clipPath id="clip0_617_8402">
                                <rect width="30" height="30" fill="white"/>
                                </clipPath>
                                </defs>
                                </svg>
                                """
            ),
        }

        # تول‌تیپ‌ها (خلاصه توضیحات مستندات)
        tooltips = {
            "status": "وضعیت تیکت را فراخوانی کنید",
            "verify": "تایید پرداخت",
            "revers": "پرداخت های موفق را میتونی با این لغو کنید. مبلغ به حساب کاربر بازگشت داده میشود",
            "cancel": "تا زمانی که تیکت در حالت پرداخت قرار دارد میتواندید آن رابا این دکمه لغو کنید",
        }

        # متن‌های دکمه‌ها
        button_texts = {
            "status": "وضعیت",
            "verify": "تأیید",
            "revers": "بازگشت",
            "cancel": "لغو",
        }

        return format_html(
            """
            <style>
                .azkivam-box {{
                    border: 1px solid #2c2c54 !important;
                    background-color: #1a1a2e !important;
                    padding: 15px !important;
                    border-radius: 12px !important;
                    margin: 5px 0 !important;
                    box-shadow: 0 2px 6px rgba(0, 128, 0, 0.1) !important;
                    position: relative !important;
                    width: 100% !important;
                    box-sizing: border-box !important;
                }}

                .azkivam-label {{
                    display: inline-block !important;
                    background-color: #0abde3 !important;
                    color: white !important;
                    padding: 4px 10px !important;
                    border-radius: 20px !important;
                    font-size: 11px !important;
                    font-weight: bold !important;
                    position: absolute !important;
                    top: -8px !important;
                    right: 10px !important;
                    z-index: 1000 !important;
                }}

                .azkivam-buttons {{
                    display: grid !important;
                    grid-template-columns: repeat(5, 1fr) !important;
                    gap: 6px !important;
                    margin-top: 8px !important;
                    width: 100% !important;
                }}

                .azkivam-buttons button:active {{
                    transform: translateY(1px) !important;
                    box-shadow: 0 1px 4px rgba(0, 123, 255, 0.3) !important;
                }}

                /* تبلت - نمایش 3 ستونه */
                @media screen and (max-width: 768px) and (min-width: 481px) {{
                    .azkivam-buttons {{
                        grid-template-columns: repeat(3, 1fr) !important;
                        gap: 8px !important;
                    }}
                    .azkivam-buttons button {{
                        min-height: 50px !important;
                        font-size: 12px !important;
                    }}
                }}

                /* موبایل بزرگ - نمایش 2 ستونه */
                @media screen and (max-width: 480px) and (min-width: 361px) {{
                    .azkivam-box {{
                        padding: 12px !important;
                    }}
                    .azkivam-buttons {{
                        grid-template-columns: repeat(2, 1fr) !important;
                        gap: 6px !important;
                    }}
                    .azkivam-buttons button {{
                        min-height: 55px !important;
                        font-size: 10px !important;
                        padding: 6px 4px !important;
                    }}
                    .azkivam-label {{
                        font-size: 10px !important;
                        padding: 3px 8px !important;
                        top: -6px !important;
                    }}
                }}

                /* موبایل کوچک */
                @media screen and (max-width: 360px) {{
                    .azkivam-box {{
                        padding: 10px !important;
                    }}
                    .azkivam-buttons {{
                        grid-template-columns: repeat(2, 1fr) !important;
                        gap: 4px !important;
                    }}
                    .azkivam-buttons button {{
                        min-height: 50px !important;
                        font-size: 9px !important;
                        padding: 4px 2px !important;
                    }}
                    .azkivam-label {{
                        font-size: 9px !important;
                        padding: 2px 6px !important;
                        top: -5px !important;
                    }}
                }}
            </style>


            <div class="azkivam-box">
                <div class="azkivam-label">درگاه پرداخت ازکی وام</div>
                <div class="azkivam-buttons">
                    <button type="button" class="azkivam-check" data-id="{0}" data-action="status"
                        title="{1}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {5}
                        <span>{11}</span>
                    </button>

                    <button type="button" class="azkivam-check" data-id="{0}" data-action="verify"
                        title="{6}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {7}
                        <span>{12}</span>
                    </button>
                    <button type="button" class="azkivam-check" data-id="{0}" data-action="revers"
                        title="{8}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {9}
                        <span>{13}</span>
                    </button>
                    <button type="button" class="azkivam-check" data-id="{0}" data-action="cancel"
                        title="{10}" style="{2}"
                        onmouseover="{3}"
                        onmouseout="{4}">
                        {14}
                        <span>{15}</span>
                    </button>
                </div>
            </div>
            """,
            obj.id,  # 0
            tooltips["status"],  # 1
            style.strip(),  # 2
            hover.strip(),  # 3
            reset_hover.strip(),  # 4
            icons["status"],  # 5
            tooltips["verify"],  # 6
            icons["verify"],  # 7
            tooltips["revers"],  # 8
            icons["revers"],  # 9
            tooltips["cancel"],  # 10
            button_texts["status"],  # 11
            button_texts["verify"],  # 12
            button_texts["revers"],  # 13
            icons["cancel"],  # 14
            button_texts["cancel"],  # 15
        )

    def handle_torob_action(self, request, order_id: int, action: str):
        try:
            order = Order.objects.get(pk=order_id)

            task_functions = {
                "verify": torobpay_verify,
                "settle": torobpay_settle,
                "revert": torobpay_revert,
                "cancel": torobpay_cancel,
                "status": torobpay_status,
            }

            if action not in task_functions:
                return JsonResponse(
                    {"status": "error", "message": "عملیات نامعتبر است"}
                )

            # اجرای مستقیم تابع
            result = task_functions[action](order)

            return JsonResponse(
                result
                or {
                    "error": f"Some error occured in request to torob pay\n result:{result}"
                }
            )

        except ObjectDoesNotExist:
            return JsonResponse({"error": "سفارش پیدا نشد"})

        except Exception as e:
            return JsonResponse({"error": f"خطا: {str(e)}"})

    def handle_snap_action(self, request, order_id: int, action: str):
        try:
            order = Order.objects.get(pk=order_id)

            task_functions = {
                "verify": snappay_verify,
                "settle": snappay_settle,
                "revert": snappay_revert,
                "cancel": snappay_cancel,
                "status": snappay_status,
            }

            if action not in task_functions:
                return JsonResponse(
                    {"status": "error", "message": "عملیات نامعتبر است"}
                )

            # اجرای مستقیم تابع
            result = task_functions[action](order)

            return JsonResponse(
                result
                or {
                    "error": f"Some error occured in request to snap pay\n result:{result}"
                }
            )

        except ObjectDoesNotExist:
            return JsonResponse({"error": "سفارش پیدا نشد"})

        except Exception as e:
            return JsonResponse({"error": f"خطا: {str(e)}"})

    def handle_azkivam_action(self, request, order_id: int, action: str):
        try:
            order = Order.objects.get(pk=order_id)

            task_functions = {
                "verify": azkivam_verify,
                "revers": azkivam_reverse,
                "cancel": azkivam_cancel,
                "status": azkivam_status,
            }

            if action not in task_functions:
                return JsonResponse(
                    {"status": "error", "message": "عملیات نامعتبر است"}
                )

            # اجرای مستقیم تابع
            result = task_functions[action](order)

            return JsonResponse(
                result
                or {
                    "error": f"Some error occured in request to torob pay\n result:{result}"
                }
            )

        except ObjectDoesNotExist:
            return JsonResponse({"error": "سفارش پیدا نشد"})

        except Exception as e:
            return JsonResponse({"error": f"خطا: {str(e)}"})

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "torob-action/<int:order_id>/<str:action>/",
                self.admin_site.admin_view(self.handle_torob_action),
                name="torob-action",
            ),
            path(
                "snap-action/<int:order_id>/<str:action>/",
                self.admin_site.admin_view(self.handle_snap_action),
                name="snap-action",
            ),
            path(
                "azkivam-action/<int:order_id>/<str:action>/",
                self.admin_site.admin_view(self.handle_azkivam_action),
                name="azkivam-action",
            ),
        ]
        return custom_urls + urls

    class Media:
        js = (
            "admin/js/torob_js/torob_fetch.js",
            "admin/js/snap_js/snap_fetch.js",
            "admin/js/azkivam_js/azkivam_fetch.js",
        )

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
    list_display = ("id", "order_link", "get_product", "quantity", "get_sold_price")
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
        "id",
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
        "id",
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
    list_display = ("id", "name", "abbreviation", "get_image", "get_products")
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
    list_display = ("id", "fa_name", "get_image", "get_products")
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
    list_display = ("id", "full_name", "get_phone_number", "request_type")
    list_filter = ("request_type",)
    search_fields = ("full_name", "phone_number")
    search_help_text = _("شما میتوانید با نام و نام خانوادگی و شماره تلفن سرچ کنید.")

    @admin.display(description=_("موبایل"))
    def get_phone_number(self, obj):
        return str(obj.phone_number).replace("+98", "0")


class OrderReceiptAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "get_authority",
        "request_code",
        "verify_code",
        "ref_id",
        "request_msg",
        "get_fee",
        "fee_type",
        "card_pan",
        "get_order",
        "azkivam_reciept",
    )
    list_filter = ("fee_type",)

    @admin.display(description=_("مالیات (تومان)"))
    def get_fee(self, obj):
        return separate_digits_and_convert_to_fa(obj.fee)

    @admin.display(description="Authority")
    def get_authority(self, obj):
        if obj and obj.authority:
            return f"Zarin Pal:{obj.authority[:3]} ... {obj.authority[-10:]}"
        if obj and obj.torob_reciept:
            return "Torob Pay"
        if obj and obj.azkivam_reciept:
            return "AzkiVam"
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
                "رسید اسنپ ترپ پی",
                {  # This section appears first
                    "fields": (
                        "snap_transaction_id",
                        "snap_error_message",
                        "snap_error_code",
                        "snap_reciept",
                    ),
                },
            ),
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
            (
                "رسید پرداخت ازکی وام",
                {
                    "fields": (
                        "azkivam_reciept",
                        "azkivam_error_message",
                    )
                },
            ),
        )


class ProductImageAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("id", "alt", "get_image", "get_same_images")
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
        "id",
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
    list_display = ("id", "get_question", "get_answer", "is_global")
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


class SMSCampaignParamAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    form = SMSCampaignParamForm
    list_display = ("id", "get_param_value", "get_campaign_name", "position")
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
    list_display = ("id", "name", "sms_template_id", "is_active", "get_params")
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
        "id",
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
admin.site.register(TroboMerchantToken)
admin.site.register(SnapPayAccessToken)
