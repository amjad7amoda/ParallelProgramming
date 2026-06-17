from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from products.permission import IsProductStoreOwner

from .models import Product
from .serializers import ProductSerializer

from store.models import Store


class ProductViewSet(ModelViewSet):

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsProductStoreOwner]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    def get_queryset(self):
        store_id = self.kwargs['store_pk']
        return Product.objects.filter(store_id=store_id)

    def perform_create(self, serializer):
        store_id = self.kwargs['store_pk']
        store = Store.objects.get(id=store_id)
        
        if store.owner != self.request.user:
            raise PermissionDenied('This store does not belong to you')

        serializer.save(store=store)