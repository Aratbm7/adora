from django.urls import path, include
from account.views import SendOtpCode, VerifyOtp, ProfileViewSet, AddressViewSet
from rest_framework_simplejwt import views as jwt_views
from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('profiles', ProfileViewSet, basename="profiles")
# router.register('addresses', AddressViewSet, basename="addresses")

profile_router =  routers.NestedDefaultRouter(router, 'profiles', lookup='profile')
profile_router.register('addresses', AddressViewSet, basename='profile-addresses' )

urlpatterns = [
    
    # path(r'^auth/', include('djoser.urls')),
    path('send_otp/', SendOtpCode.as_view(), name="send_otp"),
    path('verify_otp/', VerifyOtp.as_view(), name="verify_otp"),
    path('api/token/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
    path('', include(profile_router.urls)),
]