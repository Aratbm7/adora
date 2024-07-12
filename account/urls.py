from django.urls import path, include


urlpatterns = [
    path(r'^auth/', include('djoser.urls')),
]