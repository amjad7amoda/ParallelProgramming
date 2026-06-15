from decimal import Decimal

from django.db import transaction, OperationalError

from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework import status

from cart.models import Cart
from cart_items.models import CartItem
from order_items.models import OrderItem
from products.models import Product
from payments.models import Payment

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

        cart_item_ids = list(
            CartItem.objects.filter(cart=cart).values_list('id', flat=True)
        )
        if not cart_item_ids:
            raise ValidationError('Cart is empty')

        try:
            with transaction.atomic():
                cart_items = CartItem.objects.select_related(
                    'product', 'product__store'
                ).filter(id__in=cart_item_ids)

                total_amount = Decimal('0.00')
                locked_products = {}

                for item in cart_items:
                    product = Product.objects.select_for_update(
                        nowait=True
                    ).get(id=item.product_id)

                    if item.quantity > product.stock:
                        raise ValidationError(
                            f'Not enough stock for {product.name}. '
                            f'Available: {product.stock}, Requested: {item.quantity}'
                        )

                    total_amount += item.quantity * product.price
                    locked_products[item.product_id] = (product, item.quantity)

                order = serializer.save(user=user, status=Order.Status.PENDING)

                order_items = []
                for product, quantity in locked_products.values():
                    product.stock -= quantity
                    product.save()

                    order_items.append(OrderItem(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price
                    ))

                OrderItem.objects.bulk_create(order_items)

                Payment.objects.create(order=order, amount=total_amount)

                order.status = Order.Status.PAID
                order.save(update_fields=['status'])

                CartItem.objects.filter(cart=cart).delete()

        except OperationalError:
            raise ValidationError(
                'Another request is processing one of these products. '
                'Please try again in a moment.'
            )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.status == 'CANCELLED':
            raise ValidationError('Order already cancelled')

        try:
            with transaction.atomic():
                order_items = OrderItem.objects.select_related(
                    'product'
                ).filter(order=order)

                for item in order_items:
                    product = Product.objects.select_for_update(
                        nowait=True
                    ).get(id=item.product.id)

                    product.stock += item.quantity
                    product.save()

                order.status = 'CANCELLED'
                order.save()

        except OperationalError:
            raise ValidationError(
                'Cannot cancel right now, a transaction is in progress. '
                'Please try again.'
            )

        return Response(
            {'message': 'Order cancelled successfully'},
            status=status.HTTP_200_OK
        )