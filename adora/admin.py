import os
from django.contrib import admin    
from adora.models import *
from adora.tasks import send_order_status_message


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

def get_full_name_or_phone_number(order:Order) -> str:
    user_prfile = order.user.profile
    name = user_prfile.first_name
    last_name = user_prfile.last_name
    full_name = f"{user_prfile.first_name} {user_prfile.last_name}"
    if name or last_name:
        return full_name
    
    return str(order.user.phone_number).replace('+98', '0')

    
class OrderAdmin(admin.ModelAdmin):
    def save_model(self, request, obj:Order, form, change):
        # Check if this is an update and not a new object creation
        if change:
            # Get the previous state of the object from the database
            previous_obj: Order = self.model.objects.get(pk=obj.pk)
            # Check if `delivery_status` has changed
            # print(previous_obj.delivery_status)
            full_name = get_full_name_or_phone_number(obj)
            phone_number = str(obj.user.phone_number).replace('+98', '0')
            order_traking_number = obj.tracking_number
            print(phone_number)
            order_delivery_traking_num = obj.delivery_tracking_url
            deliver_post_name = obj.deliver_post_name

            if previous_obj.delivery_status != obj.delivery_status:
                # Call `send_message` if the new status is 'shipped' or 'pending'
                
                if obj.delivery_status == "P":
                    text_code = os.environ.get("ORDER_PENDING")
                    send_order_status_message.delay(phone_number, [full_name, order_traking_number], int(text_code))
                    print(text_code)    
                if obj.delivery_status == "S":
                    text_code = os.environ.get("ORDER_SHIPPED")
                    send_order_status_message.delay(phone_number, [full_name, order_traking_number, deliver_post_name, order_delivery_traking_num], int(text_code))


                if obj.delivery_status == "D":
                    text_code = os.environ.get("ORDER_DELIVERED")
                    send_order_status_message.delay(phone_number, [full_name, order_traking_number], int(text_code))

            rejected_reason = obj.returned_rejected_reason
            if previous_obj.returned_status != obj.returned_status:
                
                if obj.returned_status == "RC":
                    text_code = os.environ.get("ORDER_RETURNED_CONFIRM")
                    send_order_status_message.delay(phone_number, [full_name, order_traking_number], int(text_code))
                    
                if obj.returned_status == "RR":
                    text_code = os.environ.get("ORDER_RETURNED_REJECT")
                    send_order_status_message.delay(phone_number, [full_name, order_traking_number,rejected_reason], int(text_code))
                    

        # Proceed with the default save behavior
        super().save_model(request, obj, form, change)


admin.site.register(Order, OrderAdmin)
