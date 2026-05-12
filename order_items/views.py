from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from order.models import Order
from products.models import Product

from .models import OrderItem
from .permissions import IsOrderItemAccess
from .serializers import OrderItemSerializer


class OrderItemViewSet(ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated, IsOrderItemAccess]

    def get_queryset(self):
        order_id = self.kwargs['order_pk']
        user = self.request.user
        if user.role == 'CUSTOMER':
            return OrderItem.objects.filter(
                order_id=order_id,
                order__user=user
            )
        if user.role == 'STORE_OWNER':
            return OrderItem.objects.filter(
                order_id=order_id,
                order__store__owner=user
            )
        return OrderItem.objects.none()

    def perform_create(self, serializer):
        order_id = self.kwargs['order_pk']
        order = Order.objects.get(id=order_id)
        if order.user != self.request.user:
            raise ValidationError('Only the order owner can add items')
        product = serializer.validated_data['product']
        if product.store_id != order.store_id:
            raise ValidationError('Product must belong to the order store')
        serializer.save(order=order, price=product.price)
