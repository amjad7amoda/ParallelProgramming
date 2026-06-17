# stores/urls.py

from rest_framework_nested import routers

from .views import StoreViewSet
from products.views import ProductViewSet


router = routers.DefaultRouter()
router.register(r'', StoreViewSet, basename='stores')

stores_router = routers.NestedDefaultRouter(router, r'', lookup='store')
stores_router.register(r'products', ProductViewSet, basename='store-products')

urlpatterns = router.urls + stores_router.urls
