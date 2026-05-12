from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APIClient

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


class OrderViewSetTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username='owner',
            password='password',
            role='STORE_OWNER'
        )
        self.other_owner = get_user_model().objects.create_user(
            username='other_owner',
            password='password',
            role='STORE_OWNER'
        )
        self.store = Store.objects.create(
            name='Store',
            description='Test store',
            owner=self.owner
        )
        self.other_store = Store.objects.create(
            name='Other Store',
            description='Other store',
            owner=self.other_owner
        )
        self.customer = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        self.other_customer = get_user_model().objects.create_user(
            username='other_customer',
            password='password',
            role='CUSTOMER'
        )
        self.customer_order = Order.objects.create(
            user=self.customer,
            store=self.store
        )
        Order.objects.create(
            user=self.other_customer,
            store=self.other_store
        )

    def test_customer_only_sees_own_orders(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.get('/api/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['id'], self.customer_order.id)

    def test_store_owner_only_sees_store_orders(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        response = client.get('/api/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['store'], self.store.id)
