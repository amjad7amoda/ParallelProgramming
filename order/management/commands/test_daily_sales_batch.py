"""Generate test data, run the batch job, and verify the report.

Run:
    python manage.py test_daily_sales_batch --orders 40 --chunk-size 10 --workers 4

The command creates isolated data using date 2099-01-01 by default, so it will
not mix with normal daily sales reports.
"""

from decimal import Decimal
import json, os, uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from store.models import Store
from products.models import Product
from order.models import Order
from order_items.models import OrderItem
from payments.models import Payment


class Command(BaseCommand):
    help = 'Create test sales data, run the batch job, and verify totals/deadLetter.'

    def add_arguments(self, parser):
        parser.add_argument('--orders', type=int, default=40)
        parser.add_argument('--chunk-size', type=int, default=10)
        parser.add_argument('--workers', type=int, default=4)
        parser.add_argument('--date', default='2099-01-01')
        parser.add_argument('--skip-dead-letter-demo', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        tag = uuid.uuid4().hex[:8]
        day = timezone.datetime.fromisoformat(options['date']).date()
        created_at = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))

        # Build isolated test data: owner, customer, one store, three products.
        owner = User.objects.create_user(username=f'batch_owner_{tag}', password='x', role='STORE_OWNER')
        customer = User.objects.create_user(username=f'batch_customer_{tag}', password='x', role='CUSTOMER')
        store = Store.objects.create(owner=owner, name=f'Batch Store {tag}', description='batch test')
        products = [
            Product.objects.create(store=store, name=f'P{i}_{tag}', description='batch', price=price, stock=999999)
            for i, price in enumerate([Decimal('10.00'), Decimal('15.00'), Decimal('25.00')], 1)
        ]

        expected = {product.id: {'qty': 0, 'revenue': Decimal('0')} for product in products}

        # Create paid orders. Each order has two order items and one completed payment.
        for i in range(options['orders']):
            order = Order.objects.create(user=customer, store=store, status=Order.Status.PAID)
            total = Decimal('0')
            for product in (products[i % 3], products[(i + 1) % 3]):
                qty = (i % 4) + 1
                OrderItem.objects.create(order=order, product=product, quantity=qty, price=product.price)
                expected[product.id]['qty'] += qty
                expected[product.id]['revenue'] += qty * product.price
                total += qty * product.price
            payment = Payment.objects.create(order=order, amount=total, status=Payment.Status.COMPLETED)
            Payment.objects.filter(id=payment.id).update(created_at=created_at)

        # Run and verify a clean batch report.
        clean_report = os.path.join('batch_reports', f'test_daily_sales_clean_{tag}.json')
        call_command('process_daily_sales', date=str(day), chunk_size=options['chunk_size'], workers=options['workers'], output=clean_report)
        data = json.load(open(clean_report, encoding='utf-8'))
        got = {row['product_id']: row for row in data['products'] if row['product_id'] in expected}

        for product_id, exp in expected.items():
            assert got[product_id]['quantity_sold'] == exp['qty']
            assert got[product_id]['gross_revenue'] == str(exp['revenue'].quantize(Decimal('0.01')))
        assert data['deadLetter']['count'] == 0

        # Optional second run: intentionally skip one product to prove deadLetter logging.
        dead_report = ''
        if not options['skip_dead_letter_demo']:
            dead_report = os.path.join('batch_reports', f'test_daily_sales_deadletter_{tag}.json')
            call_command(
                'process_daily_sales',
                date=str(day),
                chunk_size=options['chunk_size'],
                workers=options['workers'],
                output=dead_report,
                simulate_dead_letter_product_id=products[0].id,
            )
            dead_data = json.load(open(dead_report, encoding='utf-8'))
            assert dead_data['deadLetter']['count'] > 0
            assert dead_data['failed_order_items'] == dead_data['deadLetter']['count']

        self.stdout.write(self.style.SUCCESS(
            f"TEST OK: {options['orders']} orders, {options['orders'] * 2} order items, "
            f"{data['total_chunks']} chunks, {options['workers']} threads. Clean report: {clean_report}"
        ))
        if dead_report:
            self.stdout.write(self.style.SUCCESS(f'DeadLetter demo report: {dead_report}'))
