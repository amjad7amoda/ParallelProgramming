from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import Cart


class CartModelTest(TestCase):
    def test_create_cart(self):
        user = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        cart = Cart.objects.create(user=user)
        self.assertEqual(cart.user, user)
