from rest_framework.routers import DefaultRouter
from .views import CartViewSet
from cart_items.views import CartItemViewSet

router = DefaultRouter()
router.register(r'items', CartItemViewSet, basename='cart-items') 
router.register(r'', CartViewSet, basename='cart')

urlpatterns = router.urls