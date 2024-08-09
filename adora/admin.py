from django.contrib import admin    
from adora.models import *

admin.site.site_header = "مدیریت دیتابیس  "
admin.site.site_title = " مدیریت دیتابیس "
admin.site.index_title = "به آدورا خوش آمدید"

admin.site.register(ProductImage)
admin.site.register(Category)
admin.site.register(Car)
admin.site.register(Brand)
admin.site.register(Matrial)
admin.site.register(Product)
admin.site.register(Comment)

# Register your models here.
