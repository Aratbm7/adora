from django.contrib import admin
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin
from jalali_date import  datetime2jalali
from datetime import datetime
from persian_tools import separator
from account.models import *
from django.utils.translation import gettext as _
from admin_auto_filters.filters import AutocompleteFilter
from core.utils.show_jalali_datetime import show_date_time

class UserAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("get_phone_number", "profile_link",  'get_date_joined',"orders_link",)
    search_fields = ['phone_number', 'profile__first_name', 'profile__last_name']
    search_help_text = "شما میتواند با شماره تلفن (چهار رقم اخر و انگلیسی) و نام و نام خانوادگی سرچ کنید."
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
        return (str(obj.phone_number).replace("+98", "0"))

    @admin.display(description="کیف پول")
    def get_wallet_balance(sefl, obj):
        return separator.add(int(obj.wallet_balance))


class ProfileAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):

    list_display = ("full_name", "get_addresses", "id_card", "get_wallet_balance", "orders_link")
    search_fields = ('first_name', 'last_name', 'user__phone_number')
    search_help_text = _("شما میتواند با شماره تلفن (چهار رقم اخر و انگلیسی) و نام و نام خانوادگی سرچ کنید.")

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
        return separator.add(int(obj.wallet_balance))

    @admin.display(description=_("آدرس ها"))
    def get_addresses(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/account/address/?profile__pk__exact={obj.id}",
            "آدرس ها",
        )
        
        
# class cityFilter(admin.SimpleListFilter):
#     title = _("شهر")
#     parameter_name = 'city'
    
    
#     def lookups(self, request, model_admin):
#         cities = Address.objects.values_list("city", flat=True).distinct().order_by("city")
#         return [(city, city) for city in cities if city]  # حذف مقادیر خالی

#     def queryset(self, request, queryset):
#         if self.value():
#             return queryset.filter(Q(city__icontains=self.value()))
#         return queryset

class ProfileFilter(AutocompleteFilter):
    title =_("پروفایل")
    field_name = 'profile'
class AddressAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display= ['profile', 'city', 'state', 'get_street_address']
    search_fields = ['city', 'state', 'street_address']
    search_help_text = _("میتوانید آدرس را سرچ  کنید.")
    
    list_filter = [ProfileFilter]
    
    
    @admin.display(description=_("آدرس دقیق"))
    def get_street_address(self, obj):
        return f"{obj.street_address[:20]} ..."
    
admin.site.register(User, UserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(DeliveryCost)
