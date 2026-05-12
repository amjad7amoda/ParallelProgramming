from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APIClient

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


class CartViewSetTest(TestCase):
    def test_prevent_duplicate_cart(self):
        user = get_user_model().objects.create_user(
            username='duplicate',
            password='password',
            role='CUSTOMER'
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post('/api/carts/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = client.post('/api/carts/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
