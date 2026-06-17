from django.db import transaction, OperationalError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from cart.models import Cart
from cart_items.models import CartItem
from order.locks import DistributedLockError, distributed_lock
from order.tasks import send_order_email
from order_items.models import OrderItem
from products.models import Product
from .models import Order
from .permissions import IsOrderAccess
from .serializers import OrderSerializer
from rest_framework import status


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

        product_ids = list(
            CartItem.objects.filter(id__in=cart_item_ids)
            .order_by('product_id')
            .values_list('product_id', flat=True)
            .distinct()
        )
        # مفتاح موحد يغطي كل المنتجات في نفس الطلب
        try:
            with distributed_lock(product_ids, timeout=10):
                with transaction.atomic():
                    order = serializer.save(user=user)
                    order_items = []

                    cart_items = CartItem.objects.select_related(
                        'product', 'product__store'
                    ).filter(id__in=cart_item_ids)

                    order = serializer.save(user=user)

                    locked_products = {
                        p.id: p
                        for p in Product.objects.select_for_update()
                        .filter(id__in=product_ids)
                        .order_by('id')  # ترتيب ثابت = no deadlock
                    }

                    for item in cart_items:
                        product = Product.objects.select_for_update(
                            nowait=True
                        ).get(id=item.product_id)

                        # product = Product.objects.get(id=item.product_id)

                        if item.quantity > product.stock:
                            raise ValidationError(
                                f'Not enough stock for {product.name}. '
                                f'Available: {product.stock}, Requested: {item.quantity}'
                            )

                        product.stock -= item.quantity
                        product.save()

                        order_items.append(OrderItem(
                            order=order,
                            product=product,
                            quantity=item.quantity,
                            price=product.price
                        ))
                    transaction.on_commit(
                                lambda: (
                                    send_order_email.delay(user.email, order.id)
                                )
                            )
                    OrderItem.objects.bulk_create(order_items)
                    CartItem.objects.filter(cart=cart).delete()
        except DistributedLockError:
            raise ValidationError('Product is locked')
        except OperationalError:
            raise ValidationError(
                'Another request is processing this product. '
                'Please try again in a moment.'
            )
        

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.status == 'CANCELLED':
            raise ValidationError('Order already cancelled')

        product_ids = list(
            OrderItem.objects.filter(order=order)
            .values_list('product_id', flat=True)
            .distinct()
        )

        try:
            with distributed_lock(product_ids, timeout=10):
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

        except DistributedLockError:
            raise ValidationError('Product is locked')
        except OperationalError:
            raise ValidationError(
                'Another request is processing this product. '
                'Please try again in a moment.'
            )

        return Response(
            {'message': 'Order cancelled successfully'},
            status=status.HTTP_200_OK
        )