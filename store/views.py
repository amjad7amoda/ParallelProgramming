from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from store.permissions import IsStoreOwner

from .models import Store
from .serializers import StoreSerializer


class StoreViewSet(ModelViewSet):

    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated, IsStoreOwner]

    def get_queryset(self):
        return Store.objects.all()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)