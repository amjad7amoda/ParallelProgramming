from django.shortcuts import get_object_or_404

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated

from order.models import Order

from .models import Payment
from .permissions import IsPaymentAccess
from .serializers import PaymentSerializer


class PaymentViewSet(ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsPaymentAccess]

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