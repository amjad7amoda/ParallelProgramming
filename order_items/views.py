from django.shortcuts import get_object_or_404

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

    def get_order(self):
        order_id = self.kwargs['order_pk']
        return get_object_or_404(Order, id=order_id)

    def get_queryset(self):
        order = self.get_order()
        user = self.request.user
        if user.role == 'CUSTOMER':
            if order.user != user:
                return OrderItem.objects.none()
            return OrderItem.objects.filter(order=order)
        if user.role == 'STORE_OWNER':
            if order.store.owner != user:
                return OrderItem.objects.none()
            return OrderItem.objects.filter(order=order)
        return OrderItem.objects.none()

    def perform_create(self, serializer):
        order = self.get_order()
        if order.user != self.request.user:
            raise ValidationError('Only the order owner can add items')
        product = serializer.validated_data['product']
        if product.store_id != order.store_id:
            raise ValidationError('Product must belong to the order store')
        serializer.save(order=order, price=product.price)
