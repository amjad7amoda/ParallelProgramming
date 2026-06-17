from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APIClient

from order.models import Order
from order_items.models import OrderItem
from products.models import Product
from store.models import Store

from .models import Payment


class PaymentViewSetTest(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            username='owner',
            password='password',
            role='STORE_OWNER'
        )
        self.store = Store.objects.create(
            name='Store',
            description='Test store',
            owner=owner
        )
        self.product = Product.objects.create(
            store=self.store,
            name='Item',
            description='Test product',
            price='12.50',
            stock=5
        )
        self.customer = get_user_model().objects.create_user(
            username='customer',
            password='password',
            role='CUSTOMER'
        )
        self.order = Order.objects.create(user=self.customer)
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=self.product.price
        )

    def test_create_payment_marks_order_paid(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        response = client.post(
            f'/api/orders/{self.order.id}/payment/',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.amount, Decimal('25.00'))
