from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APIClient

from order.models import Order
from products.models import Product
from store.models import Store
from .models import OrderItem


class OrderItemModelTest(TestCase):
    def test_create_order_item(self):
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
        product = Product.objects.create(
            store=store,
            name='Item',
            description='Test product',
            price='12.50',
            stock=5
        )
        customer = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        order = Order.objects.create(user=customer, store=store)
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=product.price
        )
        self.assertEqual(item.order, order)


class OrderItemViewSetTest(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            username='owner',
            password='password',
            role='STORE_OWNER'
        )
        other_owner = get_user_model().objects.create_user(
            username='other_owner',
            password='password',
            role='STORE_OWNER'
        )
        self.store = Store.objects.create(
            name='Store',
            description='Test store',
            owner=owner
        )
        self.other_store = Store.objects.create(
            name='Other Store',
            description='Other store',
            owner=other_owner
        )
        self.product = Product.objects.create(
            store=self.store,
            name='Item',
            description='Test product',
            price='12.50',
            stock=5
        )
        self.other_product = Product.objects.create(
            store=self.other_store,
            name='Other Item',
            description='Other product',
            price='7.25',
            stock=5
        )
        self.customer = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        self.order = Order.objects.create(user=self.customer, store=self.store)
        self.client = APIClient()
        self.client.force_authenticate(user=self.customer)

    def test_allow_product_from_other_store(self):
        response = self.client.post(
            f'/api/orders/{self.order.id}/items/',
            {'product': self.other_product.id, 'quantity': 1},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = OrderItem.objects.get(order=self.order, product=self.other_product)
        self.assertEqual(item.price, Decimal('7.25'))

    def test_capture_product_price(self):
        response = self.client.post(
            f'/api/orders/{self.order.id}/items/',
            {'product': self.product.id, 'quantity': 2},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = OrderItem.objects.get(order=self.order, product=self.product)
        self.assertEqual(item.price, Decimal('12.50'))

    def test_customer_cannot_view_other_order_items(self):
        other_customer = get_user_model().objects.create_user(
            username='other_customer',
            password='password',
            role='CUSTOMER'
        )
        other_order = Order.objects.create(
            user=other_customer,
            store=self.store
        )
        OrderItem.objects.create(
            order=other_order,
            product=self.product,
            quantity=1,
            price=self.product.price
        )
        response = self.client.get(f'/api/orders/{other_order.id}/items/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_store_owner_cannot_view_other_store_items(self):
        other_order = Order.objects.create(
            user=self.customer,
            store=self.other_store
        )
        OrderItem.objects.create(
            order=other_order,
            product=self.other_product,
            quantity=1,
            price=self.other_product.price
        )
        owner_client = APIClient()
        owner_client.force_authenticate(user=self.store.owner)
        response = owner_client.get(f'/api/orders/{other_order.id}/items/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])
