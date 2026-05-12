from django.test import TestCase
from django.contrib.auth import get_user_model

from store.models import Store
from .models import Order


class OrderModelTest(TestCase):
    def test_create_order(self):
        owner = get_user_model().objects.create_user(
            username='owner',
            password='password',
            role='STORE_OWNER'
        )
        store = Store.objects.create(
            name='Store',
            description='Test store',
            owner=owner
        )
        customer = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        order = Order.objects.create(user=customer, store=store)
        self.assertEqual(order.store, store)
