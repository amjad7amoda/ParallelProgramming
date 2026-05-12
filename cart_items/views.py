from django.shortcuts import get_object_or_404

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from cart.models import Cart
from .models import CartItem
from .permissions import IsCustomer, IsCartItemOwner
from .serializers import CartItemSerializer


class CartItemViewSet(ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated, IsCustomer, IsCartItemOwner]

    def get_cart(self):
        cart_id = self.kwargs['cart_pk']
        return get_object_or_404(Cart, id=cart_id)

    def get_queryset(self):
        cart = self.get_cart()
        return CartItem.objects.filter(
            cart=cart,
            cart__user=self.request.user
        )

    def perform_create(self, serializer):
        cart = self.get_cart()
        if cart.user != self.request.user:
            raise PermissionDenied('This cart does not belong to you')
        serializer.save(cart=cart)
