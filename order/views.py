from django.db import transaction

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from cart.models import Cart
from cart_items.models import CartItem
from order_items.models import OrderItem

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
            return Order.objects.filter(items__product__store__owner=user).distinct()
        return Order.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        cart = Cart.objects.filter(user=user).first()
        if not cart:
            raise ValidationError('Cart not found')
        cart_items = list(
            CartItem.objects.select_related('product', 'product__store')
            .filter(cart=cart)
        )
        if not cart_items:
            raise ValidationError('Cart is empty')
        with transaction.atomic():
            order = serializer.save(user=user)
            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                for item in cart_items
            ])
            CartItem.objects.filter(cart=cart).delete()
