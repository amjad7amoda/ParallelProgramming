from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from order.models import Order

from .models import Payment
from .permissions import IsPaymentAccess
from .serializers import PaymentSerializer


class PaymentViewSet(ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsPaymentAccess]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_order(self):
        order_id = self.kwargs['order_pk']
        return get_object_or_404(Order, id=order_id)

    def get_queryset(self):
        order = self.get_order()
        user = self.request.user
        if user.role == 'CUSTOMER' and order.user != user:
            return Payment.objects.none()
        if user.role == 'STORE_OWNER':
            if not order.items.filter(product__store__owner=user).exists():
                return Payment.objects.none()
        return Payment.objects.filter(order=order)

    def perform_create(self, serializer):
        order = self.get_order()
        if order.user != self.request.user:
            raise ValidationError('Only the order owner can pay')
        if order.status == Order.Status.PAID:
            raise ValidationError('Order is already paid')
        if not order.items.exists():
            raise ValidationError('Order has no items')
        if Payment.objects.filter(order=order).exists():
            raise ValidationError('Payment already exists for this order')
        total_amount = sum(
            (item.quantity * item.price for item in order.items.all()),
            Decimal('0.00')
        )
        with transaction.atomic():
            serializer.save(order=order, amount=total_amount)
            order.status = Order.Status.PAID
            order.save(update_fields=['status'])
