from django.contrib import admin    
from adora.models import *


admin.site.site_header = "مدیریت دیتابیس  "
admin.site.site_title = " مدیریت دیتابیس "
admin.site.index_title = "به آدورا خوش آمدید"

admin.site.register(ProductImage)
admin.site.register(Category)
admin.site.register(Car)
admin.site.register(Brand)
# admin.site.register(Matrial)
admin.site.register(Product)
admin.site.register(Comment)
admin.site.register(OrderItem)
admin.site.register(OrderProvider)
admin.site.register(Banner)
admin.site.register(OrderReceipt)
admin.site.register(Post)
admin.site.register(PostImage)
admin.site.register(Collaborate_Contact)


def send_message():
    print('hello')


class OrderAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        # Check if this is an update and not a new object creation
        if change:
            # Get the previous state of the object from the database
            previous_obj = self.model.objects.get(pk=obj.pk)
            # Check if `delivery_status` has changed
            # print(previous_obj.delivery_status)
            if previous_obj.delivery_status != obj.delivery_status:
                # Call `send_message` if the new status is 'shipped' or 'pending'
                if obj.delivery_status in ["P", "S", "D"]:
                    send_message()

        # Proceed with the default save behavior
        super().save_model(request, obj, form, change)


admin.site.register(Order, OrderAdmin)
