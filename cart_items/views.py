from django.shortcuts import get_object_or_404

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import status

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

    def create(self, request, *args, **kwargs):
        cart = self.get_cart()
        if cart.user != request.user:
            raise PermissionDenied('This cart does not belong to you')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        quantity = serializer.validated_data.get('quantity', 1)
        existing_item = CartItem.objects.filter(cart=cart, product=product).first()
        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            output = self.get_serializer(existing_item)
            return Response(output.data, status=status.HTTP_200_OK)
        serializer.save(cart=cart)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
