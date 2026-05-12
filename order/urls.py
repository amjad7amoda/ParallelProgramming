from rest_framework_nested import routers

from .views import OrderViewSet
from order_items.views import OrderItemViewSet
from payments.views import PaymentViewSet


router = routers.DefaultRouter()
router.register(r'', OrderViewSet, basename='orders')

orders_router = routers.NestedDefaultRouter(router, r'', lookup='order')
orders_router.register(r'items', OrderItemViewSet, basename='order-items')
orders_router.register(r'payment', PaymentViewSet, basename='order-payment')

urlpatterns = router.urls + orders_router.urls
