from django.contrib import admin
from account.models import *

admin.site.register(User)
admin.site.register(Profile)
admin.site.register(Address)
admin.site.register(DeliveryCost)

