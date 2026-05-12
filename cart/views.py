from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from .models import Cart
from .permissions import IsCustomer, IsCartOwner
from .serializers import CartSerializer


class CartViewSet(ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated, IsCustomer, IsCartOwner]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        raise ValidationError('Cart is created automatically for customers')
