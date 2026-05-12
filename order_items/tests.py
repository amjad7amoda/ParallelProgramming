from django.test import TestCase
from django.contrib.auth import get_user_model

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
