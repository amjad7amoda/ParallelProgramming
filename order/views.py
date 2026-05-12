from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from .models import Order
from .permissions import IsOrderAccess
from .serializers import OrderSerializer


class OrderViewSet(ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOrderAccess]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'CUSTOMER':
            return Order.objects.filter(user=user)
        if user.role == 'STORE_OWNER':
            return Order.objects.filter(store__owner=user)
        return Order.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
