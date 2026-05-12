from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APIClient

from cart.models import Cart
from cart_items.models import CartItem
from order_items.models import OrderItem
from store.models import Store
from products.models import Product
from .models import Order


class OrderModelTest(TestCase):
    def test_create_order(self):
        customer = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        order = Order.objects.create(user=customer)
        self.assertIsNone(order.store)


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
        self.other_order = Order.objects.create(
            user=self.other_customer,
            store=self.other_store
        )
        self.product = Product.objects.create(
            store=self.store,
            name='Item',
            description='Test product',
            price='10.00',
            stock=5
        )
        self.other_product = Product.objects.create(
            store=self.other_store,
            name='Other Item',
            description='Other product',
            price='7.50',
            stock=3
        )
        OrderItem.objects.create(
            order=self.customer_order,
            product=self.product,
            quantity=1,
            price=self.product.price
        )
        OrderItem.objects.create(
            order=self.other_order,
            product=self.other_product,
            quantity=1,
            price=self.other_product.price
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
        self.assertEqual(response.json()[0]['id'], self.customer_order.id)

    def test_create_order_moves_cart_items_and_clears_cart(self):
        product = Product.objects.create(
            store=self.store,
            name='Item',
            description='Test product',
            price='10.00',
            stock=5
        )
        other_product = Product.objects.create(
            store=self.store,
            name='Another Item',
            description='Another product',
            price='7.50',
            stock=3
        )
        cart = Cart.objects.get(user=self.customer)
        CartItem.objects.create(cart=cart, product=product, quantity=2)
        CartItem.objects.create(cart=cart, product=other_product, quantity=1)
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.post(
            '/api/orders/',
            {'store': self.store.id},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.json()['id'])
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 2)
        order_item = OrderItem.objects.get(order=order, product=product)
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.price, Decimal('10.00'))
        self.assertEqual(CartItem.objects.filter(cart=cart).count(), 0)
