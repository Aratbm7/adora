from django.urls import path, include
from account.views import LoginRegister

urlpatterns = [
    
    # path(r'^auth/', include('djoser.urls')),
    path('login_register/', LoginRegister.as_view(), name="login_register")
]