from core.urls.base import *  


urlpatterns += [path("__debug__/", include("debug_toolbar.urls")),]