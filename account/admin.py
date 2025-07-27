from datetime import datetime, timedelta
from typing import List

from admin_auto_filters.filters import AutocompleteFilter
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db.models import Count, Sum
from django.utils.html import format_html
from django.utils.translation import gettext as _
from jalali_date import datetime2jalali
from jalali_date.admin import ModelAdminJalaliMixin

from account.models import *
from account.tasks import (
    send_campaign_pattern_sms_with_mellipayamk,
) 
from adora.models import Order, SMSCampaign, SMSCampaignParam, SMSCampaignSendLog
from core.utils.show_jalali_datetime import show_date_time
from core.utils.separate_and_convert_to_fa import separate_digits_and_convert_to_fa

def send_sms_campaign(modeladmin, request, queryset):
    campaign_id = request.POST.get("campaign_id")
    if not campaign_id:
        messages.error(request, "لطفاً یک کمپین پیامکی انتخاب کنید.")
        return

    try:
        campaign = SMSCampaign.objects.get(id=campaign_id)
    except SMSCampaign.DoesNotExist:
        messages.error(request, "کمپین پیدا نشد.")
        return

    for user in queryset:
        send_campaign_pattern_sms_with_mellipayamk.delay(user.id, campaign.id)

    messages.success(request, f"ارسال پیامک برای {queryset.count()} کاربر آغاز شد.")


send_sms_campaign.short_description = "ارسال پیامک از کمپین انتخابی"


class SMSCampaignActionForm(ActionForm):
    campaign_id = forms.ModelChoiceField(
        queryset=SMSCampaign.objects.all(),
        required=False,
        label="کمپین پیامکی",
    )


class HasWalletBalnceFilter(admin.SimpleListFilter):
    title = _("دارای اعتبار کیف پول")
    parameter_name = "wallet_balance"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("بله")),
            ("no", _("خیر")),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(profile__wallet_balance__gt=0)
        if self.value() == "no":
            return queryset.filter(profile__wallet_balance=0)

        return queryset


class NoPurchaseLastXDaysFilter(admin.SimpleListFilter):
    title = "X روز اخیر خرید نداشته‌اند"
    parameter_name = "no_purchase_30_days"

    
    def lookups(self, request, model_admin):
        lookups = (
            ("3", "سه روز خرید نداشته اند"),
            ("7", "هفت روز خرید نداشته اند"),
            ("10", "ده روز خرید نداشته اند"),
            ("15", "پانزده روز خرید نداشته اند"),
            ("30", "سی روز خرید نداشته اند"),
        )
        return lookups

    @staticmethod
    def query(day:int) -> List[int]:
            cutoff = timezone.now() - timedelta(days=day)
            return Order.objects.filter(created_date__gte=cutoff,
                                        payment_status="C").values_list(
                "user_id", flat=True
            )
    def queryset(self, request, queryset):
        if self.value() == "3":
            return queryset.exclude(id__in=self.query(3))
        if self.value() == "7":
            return queryset.exclude(id__in=self.query(7))
        if self.value() == "10":
            return queryset.exclude(id__in=self.query(10))
        if self.value() == "15":
            return queryset.exclude(id__in=self.query(15))
        if self.value() == "30":
            return queryset.exclude(id__in=self.query(30))
        
        return queryset


class MoreThanXOrdersFilter(admin.SimpleListFilter):
    title = "بیش از ۲ خرید"
    parameter_name = "more_than_x_orders"

    @staticmethod
    def query(count:int) -> List[int]:
        return Order.objects.values("user_id")\
        .annotate(count=Count("id"))\
        .filter(count__gt=count,  payment_status="C")\
        .values_list("user_id", flat=True)
    
    def lookups(self, request, model_admin):
        return [
            ("two", "بیش از ۲ سفارش"),
            ("three", "بیش از ۳ سفارش"),
            ("four", "بیش از ۴ سفارش"),
            ("five", "بیش از ۵ سفارش"),
            ("ten", "بیش از ۱۰ سفارش"),
                                        ]

    def queryset(self, request, queryset):
        
        if self.value() == "two":
            return queryset.filter(id__in=self.query(2))
        
        if self.value() == "three":
            return queryset.filter(id__in=self.query(3))
        
        if self.value() == "four":
            return queryset.filter(id__in=self.query(4))
        
        if self.value() == "five":
            return queryset.filter(id__in=self.query(5))
        
        if self.value() == "ten":
            return queryset.filter(id__in=self.query(10))
        
        return queryset


class CartAbandonersFilter(admin.SimpleListFilter):
    title = "سبد خرید رهاشده"
    parameter_name = "cart_abandoner"

    def lookups(self, request, model_admin):
        return [("yes", "دارای سبد خرید رهاشده")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(orders__status="pending").distinct()
        return queryset


class VIPBuyersLastMonthFilter(admin.SimpleListFilter):
    title = 'VIP ماه اخیر (بالای X تومان)'
    parameter_name = 'vip_last_month'

    @staticmethod
    def query(amount:int) -> List[int]:
            start = timezone.now().replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
            return  Order.objects.filter(
                created_date__gte=start, created_date__lt=end, payment_status="C"
            ).values('user_id').annotate(total=Sum('total_price')).filter(
                total__gte=amount,
                
            ).values_list('user_id', flat=True)
    
    def lookups(self, request, model_admin):
        return [
            ('300_000', '۳۰۰ هزار تومان '),
            ('500_000', '۵۰۰ هزار تومان '),
            ('1_000_000', 'یک میلیون تومان '),
            ('2_000_000', '۲ میلیون تومان '),
            ('5_000_000', '۵ میلیون تومان '),
            ('10_000_000', '۱۰ میلیون تومان '),
            
            ]


    def queryset(self, request, queryset):
        if self.value() == '300_000':
            return queryset.filter(id__in=self.query(300_000))
        if self.value() == '500_000':
            return queryset.filter(id__in=self.query(500_000))
        if self.value() == '1_000_000':
            return queryset.filter(id__in=self.query(1_000_000))
        if self.value() == '2_000_000':
            return queryset.filter(id__in=self.query(2_000_000))
        if self.value() == '5_000_000':
            return queryset.filter(id__in=self.query(5_000_000))
        if self.value() == '10_000_000':
            return queryset.filter(id__in=self.query(10_000_000))
        
        return queryset
    
    
class OneTimeBuyersFilter(admin.SimpleListFilter):
    title = "فقط یک خرید موفق داشته اند"
    parameter_name = "one_time_buyer"

    def lookups(self, request, model_admin):
        return [("yes", "فقط یک خرید")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            user_ids = (
                Order.objects.values("user_id")
                .annotate(count=Count("id"))
                .filter(count=1, payment_status="C")
                .values_list("user_id", flat=True)
            )
            return queryset.filter(id__in=user_ids)
        return queryset


class UserAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        "get_phone_number",
        "profile_link",
        "get_date_joined",
        "orders_link",
        "get_sent_messages",
        "wallet_balance",
        "is_staff",
        "is_active",
        "is_admin",
    )
    search_fields = [ "phone_number", "profile__first_name", "profile__last_name"]
    search_help_text = "شما میتواند با شماره تلفن (چهار رقم اخر و انگلیسی) و نام و نام خانوادگی سرچ کنید."
    list_filter = (
        HasWalletBalnceFilter,
        NoPurchaseLastXDaysFilter,
        OneTimeBuyersFilter,
        VIPBuyersLastMonthFilter,
        CartAbandonersFilter,
        MoreThanXOrdersFilter,
        
        "is_staff",
        "is_active",
        "is_admin",
        # cityFilter,  # Uncomment if you want to use the city filter
    )

    actions = (send_sms_campaign,)
    action_form = SMSCampaignActionForm


    @admin.display(description="(تومان) اعتبار کیف پول")
    def wallet_balance(self, obj):
        return separate_digits_and_convert_to_fa(obj.profile.wallet_balance)

    @admin.display(description="پروفایل")
    def profile_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/profile/{obj.profile.id}/change",
            f"{obj.profile.first_name} {obj.profile.last_name}",
        )

    @admin.display(description="سفارش ها")
    def orders_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/order/?user__id={obj.id}",
            "سفارشات",
        )

    @admin.display(description="تاریخ ثبت نام")
    def get_date_joined(self, obj):
        return show_date_time(obj.date_joined)

    @admin.display(description="موبایل")
    def get_phone_number(self, obj):
        return str(obj.phone_number).replace("+98", "0")

    @admin.display(description="کیف پول")
    def get_wallet_balance(sefl, obj):
        return separate_digits_and_convert_to_fa(obj.wallet_balance)

    
    @admin.display(description="پیام های ارسال شده")
    def get_sent_messages(self, obj:User):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/smscampaignsendlog/?user__id={obj.id}",
            "پیام ها",
        )

class ProfileAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):

    list_display = (
        "full_name",
        "get_addresses",
        "id_card",
        "get_wallet_balance",
        "orders_link",
        "get_sent_messages"
    )
    search_fields = ("first_name", "last_name", "user__phone_number")
    search_help_text = _(
        "شما میتواند با شماره تلفن (چهار رقم اخر و انگلیسی) و نام و نام خانوادگی سرچ کنید."
    )

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = "نام کامل"

    @admin.display(description="سفارش ها")
    def orders_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/order/?user__id={obj.user.id}",
            "سفارشات",
        )

    @admin.display(description="کیف پول (تومان)")
    def get_wallet_balance(sefl, obj):
        return separate_digits_and_convert_to_fa(obj.wallet_balance)

    @admin.display(description=_("آدرس ها"))
    def get_addresses(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/address/?profile__pk__exact={obj.id}",
            "آدرس ها",
        )
        
    @admin.display(description="پیام های ارسال شده")
    def get_sent_messages(self, obj:Profile):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/adora/smscampaignsendlog/?user__id={obj.user.id}",
            "پیام ها",
        )



class ProfileFilter(AutocompleteFilter):
    title = _("پروفایل")
    field_name = "profile"


class AddressAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ["profile", "city", "state", "get_street_address"]
    search_fields = ["city", "state", "street_address"]
    search_help_text = _("میتوانید آدرس را سرچ  کنید.")

    list_filter = [ProfileFilter]

    @admin.display(description=_("آدرس دقیق"))
    def get_street_address(self, obj):
        return f"{obj.street_address[:20]} ..."


# admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(DeliveryCost)

