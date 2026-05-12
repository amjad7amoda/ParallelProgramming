from rest_framework_nested import routers

from .views import CartViewSet
from cart_items.views import CartItemViewSet


router = routers.DefaultRouter()
router.register(r'', CartViewSet, basename='carts')

carts_router = routers.NestedDefaultRouter(router, r'', lookup='cart')
carts_router.register(r'items', CartItemViewSet, basename='cart-items')

urlpatterns = router.urls + carts_router.urls
