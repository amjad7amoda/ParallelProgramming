from django.test import TestCase
from django.contrib.auth import get_user_model

from cart.models import Cart
from .models import CartItem
from products.models import Product
from store.models import Store


class CartItemModelTest(TestCase):
    def test_create_cart_item(self):
        owner = get_user_model().objects.create_user(
            username='owner',
            password='password',
            role='STORE_OWNER'
        )
        store = Store.objects.create(
            name='My Store',
            description='Test store',
            owner=owner
        )
        product = Product.objects.create(
            store=store,
            name='Item',
            description='Test product',
            price='9.99',
            stock=10
        )
        customer = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        cart = Cart.objects.create(user=customer)
        item = CartItem.objects.create(cart=cart, product=product, quantity=2)
        self.assertEqual(item.cart, cart)
