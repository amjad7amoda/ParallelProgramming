from rest_framework_nested import routers

from .views import OrderViewSet
from order_items.views import OrderItemViewSet


router = routers.DefaultRouter()
router.register(r'', OrderViewSet, basename='orders')

orders_router = routers.NestedDefaultRouter(router, r'', lookup='order')
orders_router.register(r'items', OrderItemViewSet, basename='order-items')

urlpatterns = router.urls + orders_router.urls
