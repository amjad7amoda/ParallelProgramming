from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/stores/', include('store.urls')),
    path('api/cart/', include('cart.urls')),
    path('api/orders/', include('order.urls'))
]
